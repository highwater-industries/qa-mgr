"""rename_organizations_to_workspaces

Revision ID: 2340b7560be3
Revises: dee8d27897c4
Create Date: 2026-01-03 10:22:34.888841

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2340b7560be3'
down_revision = 'dee8d27897c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Rename organizations to workspaces throughout the database.
    This is a comprehensive refactor to make the multi-tenancy concept more generic.
    """
    
    # Step 1: Rename user_organization_roles table to user_workspace_roles
    op.rename_table('user_organization_roles', 'user_workspace_roles')
    
    # Step 2: Rename organizations table to workspaces
    op.rename_table('organizations', 'workspaces')
    
    # Step 3: Rename columns in user_workspace_roles table
    op.alter_column('user_workspace_roles', 'organization_id', new_column_name='workspace_id')
    
    # Step 4: Rename parent_organization_id in workspaces table
    op.alter_column('workspaces', 'parent_organization_id', new_column_name='parent_workspace_id')
    
    # Step 5: Rename current_organization_id in users table
    op.alter_column('users', 'current_organization_id', new_column_name='current_workspace_id')
    
    # Step 6: Rename organization_id to workspace_id in all tables that have it
    # Check if table exists before trying to alter it
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    tables_with_org_id = [
        'projects',
        'test_suites',
        'test_cases',
        'test_runs',
        'test_results',
        'test_workers',
        'schedules',
        'notification_configs',
        'notification_logs',
        'metrics'
    ]
    
    for table in tables_with_org_id:
        if table in existing_tables:
            op.alter_column(table, 'organization_id', new_column_name='workspace_id')
    
    # Step 7: Rename indexes (conditionally based on table existence)
    # Drop old indexes and create new ones with updated names
    op.drop_index('idx_user_organization', table_name='user_workspace_roles')
    op.create_index('idx_user_workspace', 'user_workspace_roles', ['user_id', 'workspace_id'])
    
    op.drop_index('idx_organization_parent', table_name='workspaces')
    op.create_index('idx_workspace_parent', 'workspaces', ['parent_workspace_id'])
    
    if 'notification_configs' in existing_tables:
        op.drop_index('idx_notification_org_project', table_name='notification_configs')
        op.create_index('idx_notification_workspace_project', 'notification_configs', ['workspace_id', 'project_id'])
        
        op.drop_index('idx_notification_active', table_name='notification_configs')
        op.create_index('idx_notification_active', 'notification_configs', ['workspace_id', 'is_active'])


def downgrade() -> None:
    """
    Revert workspaces back to organizations.
    """
    
    # Reverse Step 7: Rename indexes back (conditionally)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'notification_configs' in existing_tables:
        op.drop_index('idx_notification_active', table_name='notification_configs')
        op.create_index('idx_notification_active', 'notification_configs', ['organization_id', 'is_active'])
        
        op.drop_index('idx_notification_workspace_project', table_name='notification_configs')
        op.create_index('idx_notification_org_project', 'notification_configs', ['organization_id', 'project_id'])
    
    op.drop_index('idx_workspace_parent', table_name='workspaces')
    op.create_index('idx_organization_parent', 'workspaces', ['parent_organization_id'])
    
    op.drop_index('idx_user_workspace', table_name='user_workspace_roles')
    op.create_index('idx_user_organization', 'user_workspace_roles', ['user_id', 'organization_id'])
    
    # Reverse Step 6: Rename workspace_id back to organization_id (conditionally)
    tables_with_workspace_id = [
        'metrics',
        'notification_logs',
        'notification_configs',
        'schedules',
        'test_workers',
        'test_results',
        'test_runs',
        'test_cases',
        'test_suites',
        'projects'
    ]
    
    for table in tables_with_workspace_id:
        if table in existing_tables:
            op.alter_column(table, 'workspace_id', new_column_name='organization_id')
    
    # Reverse Step 5: Rename current_workspace_id back in users table
    op.alter_column('users', 'current_workspace_id', new_column_name='current_organization_id')
    
    # Reverse Step 4: Rename parent_workspace_id back in organizations table
    op.alter_column('workspaces', 'parent_workspace_id', new_column_name='parent_organization_id')
    
    # Reverse Step 3: Rename columns back in user_organization_roles table
    op.alter_column('user_workspace_roles', 'workspace_id', new_column_name='organization_id')
    
    # Reverse Step 2: Rename workspaces table back to organizations
    op.rename_table('workspaces', 'organizations')
    
    # Reverse Step 1: Rename user_workspace_roles table back to user_organization_roles
    op.rename_table('user_workspace_roles', 'user_organization_roles')

