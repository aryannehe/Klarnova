from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True, index=True)
    alert_name = Column(String, index=True)
    severity = Column(String)
    priority = Column(String)
    status = Column(String, default="Open")
    namespace = Column(String)
    resource_kind = Column(String)
    resource_name = Column(String)
    description = Column(String, nullable=True)
    labels = Column(JSON, default=dict)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    detected_at = Column(DateTime(timezone=True), nullable=True)
    remediated_at = Column(DateTime(timezone=True), nullable=True)
    
    root_cause = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    requires_approval = Column(Boolean, default=False)
    state_snapshot = Column(JSON, nullable=True)

class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"))
    agent_name = Column(String, index=True)
    status = Column(String)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    inputs = Column(JSON, default=dict)
    outputs = Column(JSON, default=dict)
    
    incident = relationship("Incident")

class Remediation(Base):
    __tablename__ = "remediations"
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"))
    action = Column(String)
    incident_category = Column(String)
    outcome = Column(String)
    time_to_resolve = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class BanditPolicy(Base):
    __tablename__ = "bandit_policy"
    id = Column(Integer, primary_key=True, index=True)
    incident_category = Column(String, index=True)
    action = Column(String)
    reward = Column(Float, default=0.0)
    update_count = Column(Integer, default=0)

class Policy(Base):
    __tablename__ = "policies"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, index=True)
    severity = Column(String)
    execution_mode = Column(String) # auto, require_approval

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String) # Admin, Engineer, Viewer

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String) # User or Agent
    action = Column(String)
    target = Column(String, nullable=True)
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"
    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String, unique=True, index=True)
    doc_type = Column(String)
    content_hash = Column(String)
    last_ingested = Column(DateTime(timezone=True), server_default=func.now())
