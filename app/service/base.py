"""Base interface for all external service integrations."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, ClassVar


class ServiceInterface(ABC):
    """Base interface for all external service integrations."""

    # Class-level attribute for service type
    _service_type: ClassVar[str] = ""
    _capabilities: ClassVar[List[str]] = []

    @property
    def service_type(self) -> str:
        """Return the type of service (e.g., 'woocommerce', 'octive')"""
        return self._service_type

    @property
    def capabilities(self) -> List[str]:
        """Return a list of capabilities this service provides (e.g., 'order_query', 'product_info')"""
        return self._capabilities

    @abstractmethod
    def can_handle(self, message_purpose: str, message_details: Dict[str, Any]) -> bool:
        """Determine if this service can handle the given message purpose and details"""
        pass

    @abstractmethod
    def process_request(
        self, message_purpose: str, message_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a request and return response data"""
        pass


class ServiceRegistry:
    """Registry for service providers"""

    _instance = None
    _services: Dict[str, Type[ServiceInterface]] = {}

    def __new__(cls):
        """Singleton pattern to ensure only one registry exists"""
        if cls._instance is None:
            cls._instance = super(ServiceRegistry, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, service_class: Type[ServiceInterface]):
        """Register a service class with the registry"""
        # Get the class attribute _service_type
        service_type = getattr(service_class, "_service_type", None)
        if not service_type:
            raise ValueError(
                f"Service class {service_class.__name__} must define a _service_type class attribute"
            )

        cls._services[service_type] = service_class
        return service_class  # Return the class to allow using this as a decorator

    @classmethod
    def get_service_class(cls, service_type: str) -> Optional[Type[ServiceInterface]]:
        """Get a service class by type"""
        return cls._services.get(service_type)

    @classmethod
    def get_all_services(cls) -> Dict[str, Type[ServiceInterface]]:
        """Get all registered services"""
        return cls._services.copy()

    @classmethod
    def create_service_instance(
        cls, service_type: str, **kwargs
    ) -> Optional[ServiceInterface]:
        """Create an instance of a service by type with provided arguments"""
        service_class = cls.get_service_class(service_type)
        if service_class:
            return service_class(**kwargs)
        return None

    @classmethod
    def find_capable_service(
        cls,
        organization_services: List[Dict[str, Any]],
        message_purpose: str,
        message_details: Dict[str, Any],
        **kwargs,
    ) -> Optional[ServiceInterface]:
        """
        Find a service that can handle the given message purpose and details

        Args:
            organization_services: List of service configurations for the organization
            message_purpose: The purpose of the message
            message_details: Details extracted from the message
            **kwargs: Additional parameters to pass to service constructor

        Returns:
            An instance of a service that can handle the request, or None
        """
        for service_config in organization_services:
            service_type = service_config.get("service_type")
            if not service_type:
                continue

            service_class = cls.get_service_class(service_type)
            if not service_class:
                continue

            # Create service instance with organization-specific configuration
            service_kwargs = {**service_config, **kwargs}
            service = service_class(**service_kwargs)

            # Check if this service can handle the request
            if service.can_handle(message_purpose, message_details):
                return service

        return None
