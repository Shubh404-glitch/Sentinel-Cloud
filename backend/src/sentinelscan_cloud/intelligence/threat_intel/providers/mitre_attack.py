"""MITRE ATT&CK STIX 2.x adapter with two-pass reference resolution."""
from __future__ import annotations
from sentinelscan_cloud.intelligence.threat_intel.http_client import HTTPClient
from sentinelscan_cloud.intelligence.threat_intel.normalization import NormalizedMitreTechnique
class MitreAttackProvider:
    name="mitre_attack"
    base_url="https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json"
    def __init__(self, client=None): self.client=client or HTTPClient()
    async def fetch(self, query=None, **kwargs): return await self.client.get_json(self.base_url)
    def normalize(self, raw):
        objs = raw.get("objects", []) if isinstance(raw,dict) else []
        by_id={}
        for obj in objs:
            sid=obj.get("id")
            if sid and not obj.get("revoked",False) and not obj.get("x_mitre_deprecated",False):
                by_id[sid]=obj
        tactics={}
        for obj in by_id.values():
            if obj.get("type")=="x-mitre-tactic":
                tactics[obj["id"]]=obj.get("external_references",[{}])[0].get("external_id") or obj.get("name")
        out=[]
        for obj in by_id.values():
            if obj.get("type")!="attack-pattern": continue
            ext=next((r.get("external_id") for r in obj.get("external_references",[]) if r.get("source_name")=="mitre-attack"), None)
            if not ext: continue
            tactic_ids=[]
            for phase in obj.get("kill_chain_phases",[]):
                name=phase.get("phase_name")
                for sid,t in tactics.items():
                    if t==name: tactic_ids.append(sid)
            out.append(NormalizedMitreTechnique(ext,obj.get("name",""),obj.get("description"),tactic_ids))
        return out
