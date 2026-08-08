"""Provider registry with defensive curated fallback."""
from __future__ import annotations
from typing import Any
from sentinelscan_cloud.intelligence.threat_intel.providers.curated import CuratedProvider
from sentinelscan_cloud.intelligence.threat_intel.providers.nvd import NVDProvider
from sentinelscan_cloud.intelligence.threat_intel.providers.epss import EPSSProvider
from sentinelscan_cloud.intelligence.threat_intel.providers.kev import KEVProvider
from sentinelscan_cloud.intelligence.threat_intel.providers.mitre_attack import MitreAttackProvider

class ProviderRegistry:
    def __init__(self, settings: Any | None = None):
        self.curated=CuratedProvider()
        self.providers={"curated":self.curated}
        self.settings=settings
        if settings is not None:
            if getattr(settings,"nvd_enabled",False): self.providers["nvd"]=NVDProvider()
            if getattr(settings,"epss_enabled",False): self.providers["epss"]=EPSSProvider()
            if getattr(settings,"kev_enabled",False): self.providers["kev"]=KEVProvider()
            if getattr(settings,"mitre_attack_enabled",False): self.providers["mitre_attack"]=MitreAttackProvider()
    def register(self,name,provider): self.providers[name]=provider
    def get(self,name): return self.providers.get(name,self.curated)
    def get_with_fallback(self,name):
        provider=self.providers.get(name)
        return provider if provider is not None else self.curated
    def list_providers(self): return sorted(self.providers)
