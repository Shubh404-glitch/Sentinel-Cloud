"""Attack-chain graph construction."""
from __future__ import annotations
class AttackChainBuilder:
    def __init__(self): self.nodes=[]; self.edges=[]
    def add_node(self,node_id,node_type,**attributes):
        if not any(n["id"]==node_id for n in self.nodes):
            self.nodes.append({"id":node_id,"type":node_type,**attributes})
        return self
    def add_edge(self,source,target,relationship="related",confidence=0.0,**attributes):
        self.edges.append({"source":source,"target":target,"relationship":relationship,
                           "confidence":confidence,**attributes}); return self
    def to_graph(self): return {"nodes":self.nodes,"edges":self.edges}
