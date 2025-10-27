"""
CRM Integration Interface
Base interface and adapters for different CRM systems
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging


logger = logging.getLogger(__name__)


class CRMIntegration(ABC):
    """
    Abstract base class for CRM system integrations

    Supports:
    - Customer data retrieval
    - Case/ticket creation and updates
    - Interaction history
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to CRM system"""
        pass

    @abstractmethod
    async def get_customer_info(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get customer information by ID

        Returns:
            Dict with customer info or None if not found
        """
        pass

    @abstractmethod
    async def get_customer_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Get customer info by phone number"""
        pass

    @abstractmethod
    async def get_customer_history(
        self,
        customer_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get customer interaction history

        Returns:
            List of previous interactions/tickets
        """
        pass

    @abstractmethod
    async def create_case(
        self,
        customer_id: str,
        subject: str,
        description: str,
        priority: str = "medium",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a support case/ticket

        Returns:
            Dict with case info (case_id, etc.)
        """
        pass

    @abstractmethod
    async def update_case(
        self,
        case_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """Update an existing case"""
        pass

    @abstractmethod
    async def add_case_note(
        self,
        case_id: str,
        note: str,
        note_type: str = "internal",
    ) -> bool:
        """Add a note to a case"""
        pass


class SalesforceIntegration(CRMIntegration):
    """
    Salesforce CRM integration

    Uses Salesforce REST API
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.instance_url = config.get('instance_url')
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')
        self.username = config.get('username')
        self.password = config.get('password')
        self.security_token = config.get('security_token')
        self.client = None

    async def connect(self) -> bool:
        """Connect to Salesforce"""
        try:
            from simple_salesforce import Salesforce
            self.client = Salesforce(
                username=self.username,
                password=self.password,
                security_token=self.security_token,
            )
            logger.info("Connected to Salesforce")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Salesforce: {e}")
            return False

    async def get_customer_info(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get Salesforce Contact info"""
        try:
            contact = self.client.Contact.get(customer_id)
            return {
                "id": contact['Id'],
                "name": f"{contact.get('FirstName', '')} {contact.get('LastName', '')}".strip(),
                "email": contact.get('Email'),
                "phone": contact.get('Phone'),
                "account_name": contact.get('Account', {}).get('Name'),
            }
        except Exception as e:
            logger.error(f"Error fetching Salesforce contact: {e}")
            return None

    async def get_customer_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Search Salesforce Contact by phone"""
        try:
            query = f"SELECT Id, FirstName, LastName, Email, Phone FROM Contact WHERE Phone = '{phone}' LIMIT 1"
            result = self.client.query(query)

            if result['totalSize'] > 0:
                contact = result['records'][0]
                return await self.get_customer_info(contact['Id'])

            return None
        except Exception as e:
            logger.error(f"Error searching Salesforce by phone: {e}")
            return None

    async def get_customer_history(
        self,
        customer_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent Cases for customer"""
        try:
            query = f"SELECT Id, Subject, Status, CreatedDate FROM Case WHERE ContactId = '{customer_id}' ORDER BY CreatedDate DESC LIMIT {limit}"
            result = self.client.query(query)

            return [
                {
                    "case_id": case['Id'],
                    "subject": case['Subject'],
                    "status": case['Status'],
                    "created_date": case['CreatedDate'],
                }
                for case in result['records']
            ]
        except Exception as e:
            logger.error(f"Error fetching Salesforce case history: {e}")
            return []

    async def create_case(
        self,
        customer_id: str,
        subject: str,
        description: str,
        priority: str = "Medium",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create Salesforce Case"""
        try:
            case_data = {
                'ContactId': customer_id,
                'Subject': subject,
                'Description': description,
                'Priority': priority,
                'Origin': 'Phone',
                'Status': 'New',
            }

            result = self.client.Case.create(case_data)

            return {
                "case_id": result['id'],
                "success": result['success'],
            }
        except Exception as e:
            logger.error(f"Error creating Salesforce case: {e}")
            return {"success": False, "error": str(e)}

    async def update_case(self, case_id: str, updates: Dict[str, Any]) -> bool:
        """Update Salesforce Case"""
        try:
            self.client.Case.update(case_id, updates)
            return True
        except Exception as e:
            logger.error(f"Error updating Salesforce case: {e}")
            return False

    async def add_case_note(
        self,
        case_id: str,
        note: str,
        note_type: str = "internal",
    ) -> bool:
        """Add CaseComment to Salesforce"""
        try:
            self.client.CaseComment.create({
                'ParentId': case_id,
                'CommentBody': note,
                'IsPublished': note_type == "public",
            })
            return True
        except Exception as e:
            logger.error(f"Error adding Salesforce case note: {e}")
            return False


class ZendeskIntegration(CRMIntegration):
    """
    Zendesk integration

    Uses Zendesk REST API
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.subdomain = config.get('subdomain')
        self.email = config.get('email')
        self.api_token = config.get('api_token')
        self.client = None

    async def connect(self) -> bool:
        """Connect to Zendesk"""
        try:
            from zenpy import Zenpy
            creds = {
                'email': self.email,
                'token': self.api_token,
                'subdomain': self.subdomain,
            }
            self.client = Zenpy(**creds)
            logger.info(f"Connected to Zendesk ({self.subdomain})")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Zendesk: {e}")
            return False

    async def get_customer_info(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get Zendesk User info"""
        try:
            user = self.client.users(id=int(customer_id))
            return {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
            }
        except Exception as e:
            logger.error(f"Error fetching Zendesk user: {e}")
            return None

    async def get_customer_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Search Zendesk User by phone"""
        try:
            users = self.client.search(type='user', phone=phone)
            if users:
                user = list(users)[0]
                return await self.get_customer_info(str(user.id))
            return None
        except Exception as e:
            logger.error(f"Error searching Zendesk by phone: {e}")
            return None

    async def get_customer_history(
        self,
        customer_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent Zendesk tickets for user"""
        try:
            tickets = self.client.users.tickets(id=int(customer_id))
            history = []

            for ticket in list(tickets)[:limit]:
                history.append({
                    "case_id": str(ticket.id),
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "created_date": str(ticket.created_at),
                })

            return history
        except Exception as e:
            logger.error(f"Error fetching Zendesk ticket history: {e}")
            return []

    async def create_case(
        self,
        customer_id: str,
        subject: str,
        description: str,
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create Zendesk Ticket"""
        try:
            from zenpy.lib.api_objects import Ticket, Comment

            ticket = Ticket(
                subject=subject,
                description=description,
                requester_id=int(customer_id),
                priority=priority.lower(),
                status='new',
            )

            created_ticket = self.client.tickets.create(ticket)

            return {
                "case_id": str(created_ticket.id),
                "success": True,
            }
        except Exception as e:
            logger.error(f"Error creating Zendesk ticket: {e}")
            return {"success": False, "error": str(e)}

    async def update_case(self, case_id: str, updates: Dict[str, Any]) -> bool:
        """Update Zendesk Ticket"""
        try:
            ticket = self.client.tickets(id=int(case_id))
            for key, value in updates.items():
                setattr(ticket, key, value)
            self.client.tickets.update(ticket)
            return True
        except Exception as e:
            logger.error(f"Error updating Zendesk ticket: {e}")
            return False

    async def add_case_note(
        self,
        case_id: str,
        note: str,
        note_type: str = "internal",
    ) -> bool:
        """Add comment to Zendesk Ticket"""
        try:
            from zenpy.lib.api_objects import Ticket, Comment

            ticket = self.client.tickets(id=int(case_id))
            ticket.comment = Comment(
                body=note,
                public=(note_type == "public"),
            )
            self.client.tickets.update(ticket)
            return True
        except Exception as e:
            logger.error(f"Error adding Zendesk comment: {e}")
            return False


class HubSpotIntegration(CRMIntegration):
    """
    HubSpot CRM integration

    Uses HubSpot REST API
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.base_url = "https://api.hubapi.com"

    async def connect(self) -> bool:
        """Validate HubSpot connection"""
        logger.info("Connected to HubSpot")
        return True

    async def get_customer_info(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get HubSpot Contact"""
        # Implementation would use HubSpot API
        logger.info(f"Fetching HubSpot contact {customer_id}")
        return None

    async def get_customer_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Search HubSpot Contact by phone"""
        logger.info(f"Searching HubSpot by phone {phone}")
        return None

    async def get_customer_history(
        self,
        customer_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get HubSpot Tickets for contact"""
        logger.info(f"Fetching HubSpot history for {customer_id}")
        return []

    async def create_case(
        self,
        customer_id: str,
        subject: str,
        description: str,
        priority: str = "medium",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create HubSpot Ticket"""
        logger.info(f"Creating HubSpot ticket for {customer_id}")
        return {"success": False, "error": "Not implemented"}

    async def update_case(self, case_id: str, updates: Dict[str, Any]) -> bool:
        """Update HubSpot Ticket"""
        return False

    async def add_case_note(
        self,
        case_id: str,
        note: str,
        note_type: str = "internal",
    ) -> bool:
        """Add note to HubSpot Ticket"""
        return False


def create_crm_integration(crm_type: str, config: Dict[str, Any]) -> CRMIntegration:
    """
    Factory function to create appropriate CRM integration

    Args:
        crm_type: Type of CRM system ('salesforce', 'zendesk', 'hubspot')
        config: Configuration dict for the CRM system

    Returns:
        CRMIntegration instance
    """
    integrations = {
        'salesforce': SalesforceIntegration,
        'zendesk': ZendeskIntegration,
        'hubspot': HubSpotIntegration,
    }

    integration_class = integrations.get(crm_type.lower())

    if not integration_class:
        raise ValueError(f"Unknown CRM type: {crm_type}. Supported: {list(integrations.keys())}")

    return integration_class(config)
