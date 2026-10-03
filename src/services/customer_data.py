"""Customer data ingestion service for Customer Workflow Automation System."""

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
    CustomerSegment,
    CustomerStatus,
    CustomerType,
    PaymentStatus,
    SupportStatus,
)
from src.db.repositories import CustomerRepository
from src.db.service import get_db


@dataclass
class IngestionResult:
    """Result of customer data ingestion."""
    success: bool
    total_rows: int
    created: int
    updated: int
    errors: list[dict[str, Any]]
    message: str


@dataclass
class ValidationError:
    """Validation error for a row."""
    row_index: int
    field: str
    message: str
    value: Any


class CustomerDataService:
    """Service for customer data ingestion and validation."""
    
    # Required fields that must be present
    REQUIRED_FIELDS = ["customer_id", "name"]
    
    # All supported fields with their types
    FIELD_TYPES = {
        "customer_id": str,
        "name": str,
        "email": str,
        "phone": str,
        "company": str,
        "location": str,
        "customer_type": str,
        "lead_source": str,
        "signup_date": str,
        "last_contact_date": str,
        "last_purchase_date": str,
        "total_purchase_value": (int, float),
        "order_count": int,
        "payment_status": str,
        "outstanding_amount": (int, float),
        "support_status": str,
        "customer_status": str,
        "priority": int,
        "notes": str,
    }
    
    # Enum mappings
    CUSTOMER_TYPE_MAP = {
        "individual": CustomerType.INDIVIDUAL,
        "company": CustomerType.COMPANY,
        "enterprise": CustomerType.ENTERPRISE,
        "smb": CustomerType.SMB,
    }
    
    PAYMENT_STATUS_MAP = {
        "current": PaymentStatus.CURRENT,
        "overdue": PaymentStatus.OVERDUE,
        "partial": PaymentStatus.PARTIAL,
        "paid": PaymentStatus.PAID,
        "disputed": PaymentStatus.DISPUTED,
    }
    
    SUPPORT_STATUS_MAP = {
        "none": SupportStatus.NONE,
        "open": SupportStatus.OPEN,
        "in_progress": SupportStatus.IN_PROGRESS,
        "resolved": SupportStatus.RESOLVED,
        "escalated": SupportStatus.ESCALATED,
    }
    
    CUSTOMER_STATUS_MAP = {
        "active": CustomerStatus.ACTIVE,
        "inactive": CustomerStatus.INACTIVE,
        "prospect": CustomerStatus.PROSPECT,
        "churned": CustomerStatus.CHURNED,
        "on_hold": CustomerStatus.ON_HOLD,
    }
    
    def __init__(self, session: Optional[Any] = None):
        self.session = session
    
    def _get_session(self):
        """Get database session."""
        if self.session:
            return self.session
        # Use the database service directly to get a session
        from src.db.service import db_service
        return db_service.get_session()
    
    def _validate_row(self, row: dict, row_index: int) -> list[ValidationError]:
        """Validate a single row of customer data."""
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
        
        # Validate email format
        if "email" in row and row["email"]:
            email = str(row["email"]).strip()
            if "@" not in email or "." not in email.split("@")[-1]:
                errors.append(ValidationError(
                    row_index=row_index,
                    field="email",
                    message="Invalid email format",
                    value=email,
                ))
        
        # Validate customer_type
        if "customer_type" in row and row["customer_type"]:
            val = str(row["customer_type"]).strip().lower()
            if val not in self.CUSTOMER_TYPE_MAP:
                errors.append(ValidationError(
                    row_index=row_index,
                    field="customer_type",
                    message=f"Invalid customer_type. Must be one of: {list(self.CUSTOMER_TYPE_MAP.keys())}",
                    value=row["customer_type"],
                ))
        
        # Validate payment_status
        if "payment_status" in row and row["payment_status"]:
            val = str(row["payment_status"]).strip().lower()
            if val not in self.PAYMENT_STATUS_MAP:
                errors.append(ValidationError(
                    row_index=row_index,
                    field="payment_status",
                    message=f"Invalid payment_status. Must be one of: {list(self.PAYMENT_STATUS_MAP.keys())}",
                    value=row["payment_status"],
                ))
        
        # Validate support_status
        if "support_status" in row and row["support_status"]:
            val = str(row["support_status"]).strip().lower()
            if val not in self.SUPPORT_STATUS_MAP:
                errors.append(ValidationError(
                    row_index=row_index,
                    field="support_status",
                    message=f"Invalid support_status. Must be one of: {list(self.SUPPORT_STATUS_MAP.keys())}",
                    value=row["support_status"],
                ))
        
        # Validate customer_status
        if "customer_status" in row and row["customer_status"]:
            val = str(row["customer_status"]).strip().lower()
            if val not in self.CUSTOMER_STATUS_MAP:
                errors.append(ValidationError(
                    row_index=row_index,
                    field="customer_status",
                    message=f"Invalid customer_status. Must be one of: {list(self.CUSTOMER_STATUS_MAP.keys())}",
                    value=row["customer_status"],
                ))
        
        # Validate numeric fields
        for field in ["total_purchase_value", "outstanding_amount"]:
            if field in row and row[field] is not None and str(row[field]).strip() != "":
                try:
                    float(row[field])
                except (ValueError, TypeError):
                    errors.append(ValidationError(
                        row_index=row_index,
                        field=field,
                        message=f"'{field}' must be a number",
                        value=row[field],
                    ))
        
        if "order_count" in row and row["order_count"] is not None and str(row["order_count"]).strip() != "":
            try:
                int(row["order_count"])
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    row_index=row_index,
                    field="order_count",
                    message="'order_count' must be an integer",
                    value=row["order_count"],
                ))
        
        if "priority" in row and row["priority"] is not None and str(row["priority"]).strip() != "":
            try:
                int(row["priority"])
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    row_index=row_index,
                    field="priority",
                    message="'priority' must be an integer",
                    value=row["priority"],
                ))
        
        # Validate date fields
        for field in ["signup_date", "last_contact_date", "last_purchase_date"]:
            if field in row and row[field] is not None and str(row[field]).strip() != "":
                val = str(row[field]).strip()
                try:
                    # Try multiple date formats
                    parsed = None
                    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]:
                        try:
                            parsed = datetime.strptime(val, fmt)
                            break
                        except ValueError:
                            continue
                    if parsed is None:
                        # Try ISO format
                        parsed = datetime.fromisoformat(val.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    errors.append(ValidationError(
                        row_index=row_index,
                        field=field,
                        message=f"'{field}' has invalid date format. Use YYYY-MM-DD or ISO format",
                        value=val,
                    ))
        
        return errors
    
    def _row_to_customer(self, row: dict) -> Customer:
        """Convert a validated row to a Customer object."""
        # Parse dates
        def parse_date(val: Any) -> Optional[datetime]:
            if not val or str(val).strip() == "":
                return None
            val = str(val).strip()
            for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(val, fmt)
                except ValueError:
                    continue
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None
        
        customer = Customer(
            customer_id=str(row.get("customer_id", "")).strip(),
            name=str(row.get("name", "")).strip(),
            email=str(row.get("email", "")).strip() if row.get("email") else None,
            phone=str(row.get("phone", "")).strip() if row.get("phone") else None,
            company=str(row.get("company", "")).strip() if row.get("company") else None,
            location=str(row.get("location", "")).strip() if row.get("location") else None,
            customer_type=self.CUSTOMER_TYPE_MAP.get(
                str(row.get("customer_type", "")).strip().lower(),
                CustomerType.INDIVIDUAL
            ),
            lead_source=str(row.get("lead_source", "")).strip() if row.get("lead_source") else None,
            signup_date=parse_date(row.get("signup_date")),
            last_contact_date=parse_date(row.get("last_contact_date")),
            last_purchase_date=parse_date(row.get("last_purchase_date")),
            total_purchase_value=float(row.get("total_purchase_value", 0) or 0),
            order_count=int(row.get("order_count", 0) or 0),
            payment_status=self.PAYMENT_STATUS_MAP.get(
                str(row.get("payment_status", "")).strip().lower(),
                PaymentStatus.CURRENT
            ),
            outstanding_amount=float(row.get("outstanding_amount", 0) or 0),
            support_status=self.SUPPORT_STATUS_MAP.get(
                str(row.get("support_status", "")).strip().lower(),
                SupportStatus.NONE
            ),
            customer_status=self.CUSTOMER_STATUS_MAP.get(
                str(row.get("customer_status", "")).strip().lower(),
                CustomerStatus.PROSPECT
            ),
            priority=int(row.get("priority", 0) or 0),
            notes=str(row.get("notes", "")).strip() if row.get("notes") else None,
        )
        return customer
    
    def ingest_from_dataframe(
        self,
        df: pd.DataFrame,
        upsert: bool = True,
    ) -> IngestionResult:
        """Ingest customers from a pandas DataFrame."""
        session = self._get_session()
        repo = CustomerRepository(session)
        
        total_rows = len(df)
        created = 0
        updated = 0
        errors = []
        
        try:
            for idx, row in df.iterrows():
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
                    # Check if customer exists
                    existing = repo.get_by_customer_id(str(row_dict["customer_id"]).strip())
                    
                    customer = self._row_to_customer(row_dict)
                    
                    if existing and upsert:
                        # Update existing
                        for key, value in customer.__dict__.items():
                            if not key.startswith("_") and key != "id":
                                setattr(existing, key, value)
                        existing.updated_at = datetime.now()
                        repo.update(existing)
                        updated += 1
                    elif not existing:
                        # Create new
                        repo.create(customer)
                        created += 1
                    else:
                        # Skip if not upsert and exists
                        errors.append({
                            "row": int(idx),
                            "field": "customer_id",
                            "message": f"Customer with ID '{customer.customer_id}' already exists (upsert disabled)",
                            "value": customer.customer_id,
                        })
                        
                except Exception as e:
                    logger.error(f"Error ingesting row {idx}: {e}")
                    errors.append({
                        "row": int(idx),
                        "field": "general",
                        "message": str(e),
                        "value": row_dict.get("customer_id"),
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
            errors=errors,
            message=f"Ingested {created} new, updated {updated} existing customers. {len(errors)} errors.",
        )
    
    def ingest_from_csv(
        self,
        file_path: str | Path,
        upsert: bool = True,
        encoding: str = "utf-8",
    ) -> IngestionResult:
        """Ingest customers from a CSV file."""
        try:
            df = pd.read_csv(file_path, encoding=encoding, dtype=str)
            # Replace NaN with None
            df = df.where(pd.notnull(df), None)
            return self.ingest_from_dataframe(df, upsert=upsert)
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            return IngestionResult(
                success=False,
                total_rows=0,
                created=0,
                updated=0,
                errors=[{"row": -1, "field": "file", "message": f"Failed to read CSV: {e}", "value": str(file_path)}],
                message=f"Failed to read CSV: {e}",
            )
    
    def ingest_from_excel(
        self,
        file_path: str | Path,
        upsert: bool = True,
        sheet_name: Optional[str] = 0,
    ) -> IngestionResult:
        """Ingest customers from an Excel file."""
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=str)
            df = df.where(pd.notnull(df), None)
            return self.ingest_from_dataframe(df, upsert=upsert)
        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            return IngestionResult(
                success=False,
                total_rows=0,
                created=0,
                updated=0,
                errors=[{"row": -1, "field": "file", "message": f"Failed to read Excel: {e}", "value": str(file_path)}],
                message=f"Failed to read Excel: {e}",
            )
    
    def ingest_from_json(
        self,
        file_path: str | Path,
        upsert: bool = True,
    ) -> IngestionResult:
        """Ingest customers from a JSON file."""
        try:
            with open(file_path) as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                # Single customer object
                data = [data]
            elif not isinstance(data, list):
                raise ValueError("JSON must be an array of objects or a single object")
            
            df = pd.DataFrame(data)
            df = df.where(pd.notnull(df), None)
            return self.ingest_from_dataframe(df, upsert=upsert)
        except Exception as e:
            logger.error(f"Error reading JSON file: {e}")
            return IngestionResult(
                success=False,
                total_rows=0,
                created=0,
                updated=0,
                errors=[{"row": -1, "field": "file", "message": f"Failed to read JSON: {e}", "value": str(file_path)}],
                message=f"Failed to read JSON: {e}",
            )
    
    def ingest_from_sqlite(
        self,
        db_path: str | Path,
        table_name: str = "customers",
        upsert: bool = True,
    ) -> IngestionResult:
        """Ingest customers from another SQLite database."""
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            conn.close()
            df = df.where(pd.notnull(df), None)
            return self.ingest_from_dataframe(df, upsert=upsert)
        except Exception as e:
            logger.error(f"Error reading SQLite database: {e}")
            return IngestionResult(
                success=False,
                total_rows=0,
                created=0,
                updated=0,
                errors=[{"row": -1, "field": "file", "message": f"Failed to read SQLite: {e}", "value": str(db_path)}],
                message=f"Failed to read SQLite: {e}",
            )
    
    def export_to_csv(
        self,
        file_path: str | Path,
        filters: Optional[dict] = None,
    ) -> IngestionResult:
        """Export customers to CSV."""
        session = self._get_session()
        repo = CustomerRepository(session)
        
        try:
            customers = repo.list_customers(limit=10000, filters=filters)
            
            if not customers:
                return IngestionResult(
                    success=True,
                    total_rows=0,
                    created=0,
                    updated=0,
                    errors=[],
                    message="No customers to export",
                )
            
            # Convert to DataFrame
            data = []
            for c in customers:
                data.append({
                    "customer_id": c.customer_id,
                    "name": c.name,
                    "email": c.email,
                    "phone": c.phone,
                    "company": c.company,
                    "location": c.location,
                    "customer_type": c.customer_type.value,
                    "lead_source": c.lead_source,
                    "signup_date": c.signup_date.isoformat() if c.signup_date else "",
                    "last_contact_date": c.last_contact_date.isoformat() if c.last_contact_date else "",
                    "last_purchase_date": c.last_purchase_date.isoformat() if c.last_purchase_date else "",
                    "total_purchase_value": c.total_purchase_value,
                    "order_count": c.order_count,
                    "payment_status": c.payment_status.value,
                    "outstanding_amount": c.outstanding_amount,
                    "support_status": c.support_status.value,
                    "customer_status": c.customer_status.value,
                    "customer_segment": c.customer_segment.value if c.customer_segment else "",
                    "priority": c.priority,
                    "engagement_score": c.engagement_score,
                    "value_score": c.value_score,
                    "churn_risk": c.churn_risk,
                    "follow_up_priority": c.follow_up_priority,
                    "notes": c.notes,
                })
            
            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False)
            
            return IngestionResult(
                success=True,
                total_rows=len(data),
                created=0,
                updated=0,
                errors=[],
                message=f"Exported {len(data)} customers to {file_path}",
            )
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return IngestionResult(
                success=False,
                total_rows=0,
                created=0,
                updated=0,
                errors=[{"row": -1, "field": "file", "message": f"Failed to export CSV: {e}", "value": str(file_path)}],
                message=f"Failed to export CSV: {e}",
            )
    
    def get_sample_template(self) -> str:
        """Get a CSV template for customer data."""
        template = """customer_id,name,email,phone,company,location,customer_type,lead_source,signup_date,last_contact_date,last_purchase_date,total_purchase_value,order_count,payment_status,outstanding_amount,support_status,customer_status,priority,notes
CUST001,John Doe,john@example.com,+1-555-0100,Acme Corp,New York,company,website,2024-01-15,2024-12-01,2024-11-15,5000.00,10,current,0.00,none,active,10,VIP customer
CUST002,Jane Smith,jane@example.com,+1-555-0200,Globex Inc,San Francisco,company,referral,2024-03-20,2024-11-28,2024-10-01,15000.00,25,current,0.00,none,active,20,High value
CUST003,Bob Wilson,bob@example.com,+1-555-0300,,Chicago,individual,social_media,2024-06-10,2024-10-15,,0.00,0,overdue,500.00,open,inactive,5,Needs follow-up
"""
        return template


def create_customer_data_service(session: Optional[Any] = None) -> CustomerDataService:
    """Factory function to create customer data service."""
    return CustomerDataService(session)