-- Alpha initial schema v1. Add future migrations; do not edit a deployed baseline.


CREATE TABLE accounts (
	id VARCHAR(36) NOT NULL, 
	username VARCHAR(100) NOT NULL, 
	password_hash VARCHAR(256) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
)

;


CREATE TABLE schema_versions (
	version SERIAL NOT NULL, 
	installed_at VARCHAR(40) NOT NULL, 
	PRIMARY KEY (version)
)

;


CREATE TABLE entities (
	tenant_id VARCHAR(36) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	kind VARCHAR(24) NOT NULL, 
	version INTEGER NOT NULL, 
	revision INTEGER NOT NULL, 
	deleted BOOLEAN NOT NULL, 
	client_id VARCHAR(36), 
	related_id VARCHAR(36), 
	source_id VARCHAR(36), 
	created_at VARCHAR(40) NOT NULL, 
	payload BYTEA NOT NULL, 
	PRIMARY KEY (tenant_id, id), 
	FOREIGN KEY(tenant_id) REFERENCES accounts (id), 
	FOREIGN KEY(tenant_id, related_id) REFERENCES entities (tenant_id, id), 
	FOREIGN KEY(tenant_id, source_id) REFERENCES entities (tenant_id, id), 
	UNIQUE (tenant_id, kind, client_id)
)

;

CREATE INDEX ix_entities_kind ON entities (kind);

CREATE INDEX ix_entities_tenant_kind_time ON entities (tenant_id, kind, created_at);


CREATE TABLE sessions (
	token_hash VARCHAR(64) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	expires_at VARCHAR(40) NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(tenant_id) REFERENCES accounts (id)
)

;


CREATE TABLE audio_blobs (
	tenant_id VARCHAR(36) NOT NULL, 
	record_id VARCHAR(36) NOT NULL, 
	payload BYTEA NOT NULL, 
	PRIMARY KEY (tenant_id, record_id), 
	FOREIGN KEY(tenant_id, record_id) REFERENCES entities (tenant_id, id)
)

;


CREATE TABLE jobs (
	tenant_id VARCHAR(36) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	record_id VARCHAR(36) NOT NULL, 
	revision INTEGER NOT NULL, 
	state VARCHAR(24) NOT NULL, 
	fence INTEGER NOT NULL, 
	lease_until VARCHAR(40), 
	attempts INTEGER NOT NULL, 
	error_code VARCHAR(40), 
	PRIMARY KEY (tenant_id, id), 
	FOREIGN KEY(tenant_id, record_id) REFERENCES entities (tenant_id, id), 
	UNIQUE (tenant_id, record_id, revision)
)

;

CREATE INDEX ix_jobs_claim ON jobs (state, lease_until);


CREATE TABLE stage_usage (
	tenant_id VARCHAR(36) NOT NULL, 
	record_id VARCHAR(36) NOT NULL, 
	revision INTEGER NOT NULL, 
	stage VARCHAR(24) NOT NULL, 
	units INTEGER NOT NULL, 
	completed_at VARCHAR(40) NOT NULL, 
	PRIMARY KEY (tenant_id, record_id, revision, stage), 
	FOREIGN KEY(tenant_id, record_id) REFERENCES entities (tenant_id, id)
)

;


CREATE TABLE outbox (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	job_id VARCHAR(36) NOT NULL, 
	created_at VARCHAR(40) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id, job_id) REFERENCES jobs (tenant_id, id)
)

;
