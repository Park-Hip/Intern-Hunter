from .agent_routes import router as agent_api_router
from .demo_routes import router as demo_api_router

# Compatibility alias for older imports that expect `router`.
router = demo_api_router

__all__ = ["agent_api_router", "demo_api_router", "router"]
