"""Ticket data ingestion service for Customer Workflow Automation System."""

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.config.logging_config import logger
from src.db.models import (
    Customer,
    Ticket,
    TicketPriority,
    TicketQueue,
    TicketStatus,
    TicketType,
)
from src.db.repositories import CustomerRepository, TicketRepository
from src.db.service import get_db


@dataclass
class IngestionResult:
    """Result of ticket data ingestion."""

    success: bool
    total_rows: int
    created: int
    updated: int
    skipped: int
    errors: list[dict[str, Any]]
    message: str


@dataclass
class ValidationError:
    """Validation error for a row."""

    row_index: int
    field: str
    message: str
    value: Any


class TicketDataService:
    """Service for ticket data ingestion and validation."""

    # Required fields that must be present
    REQUIRED_FIELDS = ["subject", "body"]

    # All supported fields with their types
    FIELD_TYPES = {
        "ticket_id": str,
        "customer_id": str,
        "subject": str,
        "body": str,
        "answer": str,
        "type": str,
        "queue": str,
        "priority": str,
        "language": str,
        "tag_1": str,
        "tag_2": str,
        "tag_3": str,
        "tag_4": str,
        "tag_5": str,
        "tag_6": str,
        "tag_7": str,
        "tag_8": str,
    }

    # Enum mappings
    TICKET_TYPE_MAP = {
        "incident": TicketType.INCIDENT,
        "request": TicketType.REQUEST,
        "problem": TicketType.PROBLEM,
        "question": TicketType.QUESTION,
        "change": TicketType.INCIDENT,  # Map Change to Incident as it's a change request/incident
    }

    TICKET_PRIORITY_MAP = {
        "low": TicketPriority.LOW,
        "medium": TicketPriority.MEDIUM,
        "high": TicketPriority.HIGH,
        "critical": TicketPriority.CRITICAL,
    }

    TICKET_QUEUE_MAP = {
        "technical support": TicketQueue.TECHNICAL_SUPPORT,
        "billing and payments": TicketQueue.BILLING_PAYMENTS,
        "returns and exchanges": TicketQueue.RETURNS_EXCHANGES,
        "sales and pre-sales": TicketQueue.SALES_PRESALES,
        "general": TicketQueue.GENERAL,
        "customer service": TicketQueue.TECHNICAL_SUPPORT,
        "general inquiry": TicketQueue.GENERAL,
        "human resources": TicketQueue.GENERAL,
        "it support": TicketQueue.TECHNICAL_SUPPORT,
        "product support": TicketQueue.TECHNICAL_SUPPORT,
        "service outages and maintenance": TicketQueue.TECHNICAL_SUPPORT,
    }

    TICKET_STATUS_MAP = {
        "open": TicketStatus.OPEN,
        "in_progress": TicketStatus.IN_PROGRESS,
        "pending_customer": TicketStatus.PENDING_CUSTOMER,
        "resolved": TicketStatus.RESOLVED,
        "closed": TicketStatus.CLOSED,
        "cancelled": TicketStatus.CANCELLED,
    }

    def __init__(self, session: Optional[Any] = None):
        self.session = session

    def _get_session(self):
        """Get database session."""
        if self.session:
            return self.session
        from src.db.service import db_service
        return db_service.get_session()

    def _validate_row(self, row: dict, row_index: int) -> list[ValidationError]:
        """Validate a single row of ticket data."""
        errors = []

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in row or not row[field] or str(row[field]).strip() == "":
                errors.append(ValidationError(
                    row_index=row_index,
                    field=field,
                    message=f"Required field '{field}' is missing or empty",
                    value=row.get(field),
                ))

        # Validate ticket_type
        if "type" in row and row["type"]:
            val = str(row["type"]).strip().lower()
            if val not in self.TICKET_TYPE_MAP:
                errors.append(ValidationError(
                    row_index=row_index,
                    field="type",
                    message=f"Invalid type. Must be one of: {list(self.TICKET_TYPE_MAP.keys())}",
                    value=row["type"],
                ))

        # Validate priority
        if "priority" in row and row["priority"]:
            val = str(row["priority"]).strip().lower()
            if val not in self.TICKET_PRIORITY_MAP:
                errors.append(ValidationError(
                    row_index=row_index,
                    field="priority",
                    message=f"Invalid priority. Must be one of: {list(self.TICKET_PRIORITY_MAP.keys())}",
                    value=row["priority"],
                ))

        # Validate queue
        if "queue" in row and row["queue"]:
            val = str(row["queue"]).strip().lower()
            if val not in self.TICKET_QUEUE_MAP:
                errors.append(ValidationError(
                    row_index=row_index,
                    field="queue",
                    message=f"Invalid queue. Must be one of: {list(self.TICKET_QUEUE_MAP.keys())}",
                    value=row["queue"],
                ))

        # Validate language
        if "language" in row and row["language"]:
            val = str(row["language"]).strip().lower()
            if len(val) not in [2, 3, 5]:  # ISO language codes (en, de, en-US, etc.)
                errors.append(ValidationError(
                    row_index=row_index,
                    field="language",
                    message=f"Invalid language code format",
                    value=row["language"],
                ))

        return errors

    def _build_tags(self, row: dict) -> Optional[list]:
        """Build tags list from tag_1 through tag_8 columns."""
        tags = []
        for i in range(1, 9):
            tag_key = f"tag_{i}"
            if tag_key in row and row[tag_key] and str(row[tag_key]).strip().lower() != "none":
                tags.append(str(row[tag_key]).strip())
        return tags if tags else None

    def _resolve_customer(self, customer_repo: CustomerRepository, row: dict) -> Optional[int]:
        """
        Try to resolve customer from ticket data.
        Priority: customer_id field > email in body/subject > name matching
        """
        # Try explicit customer_id field
        if "customer_id" in row and row["customer_id"]:
            customer_id = str(row["customer_id"]).strip()
            customer = customer_repo.get_by_customer_id(customer_id)
            if customer:
                return customer.id

        # Try to find customer by email mentioned in body/subject
        import re
        text = f"{row.get('subject', '')} {row.get('body', '')}"
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, text)
        for email in emails:
            customer = customer_repo.get_by_email(email)
            if customer:
                return customer.id

        return None

    def _row_to_ticket(self, row: dict, customer_id: Optional[int], ticket_id: str) -> Ticket:
        """Convert a validated row to a Ticket object."""
        # Parse type
        ticket_type = TicketType.REQUEST
        if "type" in row and row["type"]:
            ticket_type = self.TICKET_TYPE_MAP.get(
                str(row["type"]).strip().lower(), TicketType.REQUEST
            )

        # Parse priority
        priority = TicketPriority.MEDIUM
        if "priority" in row and row["priority"]:
            priority = self.TICKET_PRIORITY_MAP.get(
                str(row["priority"]).strip().lower(), TicketPriority.MEDIUM
            )

        # Parse queue
        queue = TicketQueue.GENERAL
        if "queue" in row and row["queue"]:
            queue = self.TICKET_QUEUE_MAP.get(
                str(row["queue"]).strip().lower(), TicketQueue.GENERAL
            )

        # Parse status (default to OPEN for new tickets)
        status = TicketStatus.OPEN

        # Parse language
        language = None
        if "language" in row and row["language"]:
            language = str(row["language"]).strip().lower()

        # Build tags
        tags = self._build_tags(row)

        # Build description from body
        description = str(row.get("body", "")).strip()
        if "answer" in row and row["answer"]:
            description += f"\n\n--- Answer ---\n{str(row['answer']).strip()}"

        # Subject
        subject = str(row.get("subject", "")).strip()

        return Ticket(
            ticket_id=ticket_id,
            customer_id=customer_id,
            subject=subject,
            description=description,
            resolution=None,  # Will be populated when resolved
            ticket_type=ticket_type,
            queue=queue,
            priority=priority,
            status=status,
            language=language,
            tags=tags,
            source="huggingface_dataset",
        )

    def ingest_from_dataframe(
        self,
        df: pd.DataFrame,
        max_rows: Optional[int] = None,
        upsert: bool = True,
    ) -> IngestionResult:
        """Ingest tickets from a pandas DataFrame."""
        session = self._get_session()
        ticket_repo = TicketRepository(session)
        customer_repo = CustomerRepository(session)

        total_rows = len(df)
        if max_rows:
            total_rows = min(total_rows, max_rows)
            df = df.head(max_rows)

        created = 0
        updated = 0
        skipped = 0
        errors = []

        try:
            for idx, row in df.iterrows():
                if max_rows and idx >= max_rows:
                    break

                row_dict = row.to_dict()

                # Validate
                validation_errors = self._validate_row(row_dict, idx)
                if validation_errors:
                    for err in validation_errors:
                        errors.append({
                            "row": int(idx),
                            "field": err.field,
                            "message": err.message,
                            "value": err.value,
                        })
                    continue

                try:
                    # Generate ticket_id if not provided
                    ticket_id = row_dict.get("ticket_id")
                    if not ticket_id or str(ticket_id).strip() == "" or str(ticket_id).lower() == "nan":
                        ticket_id = f"TKT-{idx:06d}"
                    else:
                        ticket_id = str(ticket_id).strip()

                    # Check if ticket already exists
                    existing = ticket_repo.get_by_ticket_id(ticket_id)

                    # Try to resolve customer
                    customer_id = self._resolve_customer(customer_repo, row_dict)

                    ticket = self._row_to_ticket(row_dict, customer_id, ticket_id)

                    if existing and upsert:
                        # Update existing
                        for key, value in ticket.__dict__.items():
                            if not key.startswith("_") and key != "id":
                                setattr(existing, key, value)
                        existing.updated_at = datetime.now()
                        ticket_repo.update(existing)
                        updated += 1
                    elif not existing:
                        # Create new
                        ticket_repo.create(ticket)
                        created += 1
                    else:
                        # Skip if not upsert and exists
                        skipped += 1
                        errors.append({
                            "row": int(idx),
                            "field": "ticket_id",
                            "message": f"Ticket with ID '{ticket_id}' already exists (upsert disabled)",
                            "value": ticket_id,
                        })

                except Exception as e:
                    logger.error(f"Error ingesting row {idx}: {e}")
                    errors.append({
                        "row": int(idx),
                        "field": "general",
                        "message": str(e),
                        "value": row_dict.get("ticket_id") or row_dict.get("subject", "unknown"),
                    })

            # Commit all changes
            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Error during ingestion: {e}")
            errors.append({
                "row": -1,
                "field": "general",
                "message": f"Transaction failed: {e}",
                "value": "",
            })
            raise
        finally:
            session.close()

        return IngestionResult(
            success=len(errors) == 0,
            total_rows=total_rows,
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
            message=f"Ingested {created} new, updated {updated} existing, skipped {skipped} tickets. {len(errors)} errors.",
        )

    def ingest_from_csv(
        self,
        file_path: str | Path,
        max_rows: Optional[int] = None,
        upsert: bool = True,
        encoding: str = "utf-8",
    ) -> IngestionResult:
        """Ingest tickets from a CSV file."""
        try:
            df = pd.read_csv(file_path, encoding=encoding, dtype=str)
            # Replace NaN with None
            df = df.where(pd.notnull(df), None)
            return self.ingest_from_dataframe(df, max_rows=max_rows, upsert=upsert)
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            return IngestionResult(
                success=False,
                total_rows=0,
                created=0,
                updated=0,
                skipped=0,
                errors=[{"row": -1, "field": "file", "message": f"Failed to read CSV: {e}", "value": str(file_path)}],
                message=f"Failed to read CSV: {e}",
            )

    def ingest_from_huggingface(
        self,
        dataset_name: str = "Tobi-Bueck/customer-support-tickets",
        split: str = "train",
        max_rows: int = 1000,
        upsert: bool = True,
    ) -> IngestionResult:
        """Ingest tickets directly from Hugging Face dataset."""
        try:
            from datasets import load_dataset
            logger.info(f"Loading dataset {dataset_name} (split: {split}, max_rows: {max_rows})")
            
            # Load the dataset
            ds = load_dataset(dataset_name, split=split)
            
            # Limit rows
            if max_rows and max_rows < len(ds):
                ds = ds.select(range(max_rows))
            
            # Convert to DataFrame
            df = ds.to_pandas()
            df = df.where(pd.notnull(df), None)
            
            return self.ingest_from_dataframe(df, max_rows=None, upsert=upsert)
        except Exception as e:
            logger.error(f"Error loading Hugging Face dataset: {e}")
            return IngestionResult(
                success=False,
                total_rows=0,
                created=0,
                updated=0,
                skipped=0,
                errors=[{"row": -1, "field": "dataset", "message": f"Failed to load dataset: {e}", "value": dataset_name}],
                message=f"Failed to load dataset: {e}",
            )


def create_ticket_data_service(session: Optional[Any] = None) -> TicketDataService:
    """Factory function to create ticket data service."""
    return TicketDataService(session)