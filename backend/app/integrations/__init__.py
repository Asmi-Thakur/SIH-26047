"""Provider adapter package.

Every external capability is represented by a Protocol in ``base.py``. Concrete
adapters are added per phase (mock first, then vendors) and selected through
configuration (``DEMO_MODE=true`` -> mocks). Callers depend on the Protocol
only — see ARCHITECTURE.md "Provider abstraction philosophy".
"""
