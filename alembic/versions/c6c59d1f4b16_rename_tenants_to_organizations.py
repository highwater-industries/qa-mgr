"""Rename tenants to organizations

Revision ID: c6c59d1f4b16
Revises: f035cde61025
Create Date: 2026-01-01 21:49:08.509563

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6c59d1f4b16'
down_revision = 'f035cde61025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename tables
    op.rename_table('tenants', 'organizations')
    op.rename_table('user_tenant_roles', 'user_organization_roles')
    
    # Update foreign key column names for clarity
    op.alter_column('organizations', 'parent_id', 
                    new_column_name='parent_organization_id')
    op.alter_column('user_organization_roles', 'tenant_id', 
                    new_column_name='organization_id')
    op.alter_column('users', 'current_tenant_id', 
                    new_column_name='current_organization_id')
    op.alter_column('projects', 'tenant_id', 
                    new_column_name='organization_id')
    op.alter_column('test_suites', 'tenant_id', 
                    new_column_name='organization_id')
    op.alter_column('api_tokens', 'tenant_id', 
                    new_column_name='organization_id')
    op.alter_column('audit_logs', 'tenant_id', 
                    new_column_name='organization_id')
    op.alter_column('worker_templates', 'tenant_id', 
                    new_column_name='organization_id')
    op.alter_column('system_events', 'tenant_id', 
                    new_column_name='organization_id')
    
    # Rename indexes
    op.execute("ALTER INDEX idx_tenant_parent RENAME TO idx_organization_parent")
    op.execute("ALTER INDEX idx_tenant_slug RENAME TO idx_organization_slug")
    op.execute("ALTER INDEX idx_user_tenant RENAME TO idx_user_organization")
    op.execute("ALTER INDEX idx_unique_user_tenant RENAME TO idx_unique_user_organization")
    op.execute("ALTER INDEX idx_project_tenant RENAME TO idx_project_organization")
    op.execute("ALTER INDEX idx_project_tenant_name RENAME TO idx_project_organization_name")
    op.execute("ALTER INDEX idx_suite_tenant_project RENAME TO idx_suite_organization_project")
    op.execute("ALTER INDEX idx_suite_path RENAME TO idx_suite_organization_path")
    op.execute("ALTER INDEX idx_token_tenant_user RENAME TO idx_token_organization_user")
    op.execute("ALTER INDEX idx_token_active RENAME TO idx_token_organization_active")
    op.execute("ALTER INDEX idx_audit_tenant_action RENAME TO idx_audit_organization_action")
    op.execute("ALTER INDEX idx_audit_tenant_resource RENAME TO idx_audit_organization_resource")
    op.execute("ALTER INDEX idx_system_event_tenant RENAME TO idx_system_event_organization")
    op.execute("ALTER INDEX idx_template_tenant_type RENAME TO idx_template_organization_type")
    op.execute("ALTER INDEX idx_template_active RENAME TO idx_template_organization_active")


def downgrade() -> None:
    # Reverse all changes
    op.execute("ALTER INDEX idx_organization_parent RENAME TO idx_tenant_parent")
    op.execute("ALTER INDEX idx_organization_slug RENAME TO idx_tenant_slug")
    op.execute("ALTER INDEX idx_user_organization RENAME TO idx_user_tenant")
    op.execute("ALTER INDEX idx_unique_user_organization RENAME TO idx_unique_user_tenant")
    op.execute("ALTER INDEX idx_project_organization RENAME TO idx_project_tenant")
    op.execute("ALTER INDEX idx_project_organization_name RENAME TO idx_project_tenant_name")
    op.execute("ALTER INDEX idx_suite_organization_project RENAME TO idx_suite_tenant_project")
    op.execute("ALTER INDEX idx_suite_organization_path RENAME TO idx_suite_path")
    op.execute("ALTER INDEX idx_token_organization_user RENAME TO idx_token_tenant_user")
    op.execute("ALTER INDEX idx_token_organization_active RENAME TO idx_token_active")
    op.execute("ALTER INDEX idx_audit_organization_action RENAME TO idx_audit_tenant_action")
    op.execute("ALTER INDEX idx_audit_organization_resource RENAME TO idx_audit_tenant_resource")
    op.execute("ALTER INDEX idx_system_event_organization RENAME TO idx_system_event_tenant")
    op.execute("ALTER INDEX idx_template_organization_type RENAME TO idx_template_tenant_type")
    op.execute("ALTER INDEX idx_template_organization_active RENAME TO idx_template_active")
    
    op.alter_column('system_events', 'organization_id', 
                    new_column_name='tenant_id')
    op.alter_column('worker_templates', 'organization_id', 
                    new_column_name='tenant_id')
    op.alter_column('audit_logs', 'organization_id', 
                    new_column_name='tenant_id')
    op.alter_column('api_tokens', 'organization_id', 
                    new_column_name='tenant_id')
    op.alter_column('test_suites', 'organization_id', 
                    new_column_name='tenant_id')
    op.alter_column('projects', 'organization_id', 
                    new_column_name='tenant_id')
    op.alter_column('users', 'current_organization_id', 
                    new_column_name='current_tenant_id')
    op.alter_column('user_organization_roles', 'organization_id', 
                    new_column_name='tenant_id')
    op.alter_column('organizations', 'parent_organization_id', 
                    new_column_name='parent_id')
    
    op.rename_table('user_organization_roles', 'user_tenant_roles')
    op.rename_table('organizations', 'tenants')

