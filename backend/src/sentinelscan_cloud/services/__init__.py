"""Application/service layer (Section 9: Backend Architecture -- the API
layer is thin and delegates to this layer, which is the only place
business logic that spans more than one repository call is allowed to
live)."""
from __future__ import annotations
