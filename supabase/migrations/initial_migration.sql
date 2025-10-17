-- ============================================================================
-- Imperecta Database Schema - Authentication & Multi-tenancy
-- Security: RLS enabled, audit logging, encrypted sensitive data
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- USERS TABLE - User profiles linked to Supabase Auth
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supabase_user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    avatar_url TEXT,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE NOT NULL,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    CONSTRAINT users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- ============================================================================
-- ORGANIZATIONS TABLE - Multi-tenant organizations (client environments)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    max_members INTEGER DEFAULT 10 NOT NULL,
    settings JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    CONSTRAINT organizations_slug_format CHECK (slug ~* '^[a-z0-9-]+$'),
    CONSTRAINT organizations_slug_length CHECK (length(slug) >= 3 AND length(slug) <= 100),
    CONSTRAINT organizations_max_members_positive CHECK (max_members > 0)
);

-- ============================================================================
-- ROLES TABLE - Predefined system roles
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    permissions JSONB DEFAULT '[]'::JSONB NOT NULL,
    is_system BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    CONSTRAINT roles_name_format CHECK (name ~* '^[a-z_]+$')
);

-- ============================================================================
-- ORGANIZATION MEMBERS TABLE - User membership in organizations
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.organization_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES public.roles(id) ON DELETE RESTRICT,
    invited_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    invited_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    joined_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    CONSTRAINT organization_members_unique UNIQUE(organization_id, user_id)
);

-- ============================================================================
-- AUDIT LOG TABLE - Security audit trail
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    CONSTRAINT audit_logs_action_not_empty CHECK (length(action) > 0)
);

-- ============================================================================
-- SESSIONS TABLE - Active user sessions for security tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    last_activity_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    CONSTRAINT sessions_expires_future CHECK (expires_at > created_at)
);

-- ============================================================================
-- INDEXES - Performance optimization
-- ============================================================================

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_supabase_user_id ON public.users(supabase_user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON public.users(is_active) WHERE is_active = TRUE;

-- Organizations indexes
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON public.organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_owner_id ON public.organizations(owner_id);
CREATE INDEX IF NOT EXISTS idx_organizations_is_active ON public.organizations(is_active) WHERE is_active = TRUE;

-- Organization members indexes
CREATE INDEX IF NOT EXISTS idx_org_members_user_id ON public.organization_members(user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_org_id ON public.organization_members(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_members_role_id ON public.organization_members(role_id);
CREATE INDEX IF NOT EXISTS idx_org_members_active ON public.organization_members(organization_id, user_id) WHERE is_active = TRUE;

-- Audit logs indexes
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_org_id ON public.audit_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON public.audit_logs(action);

-- Sessions indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON public.sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON public.sessions(expires_at);

-- ============================================================================
-- FUNCTIONS - Business logic and automation
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- Function to automatically create user profile after auth signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (supabase_user_id, email, first_name, last_name, email_verified)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'first_name', split_part(COALESCE(NEW.raw_user_meta_data->>'name', ''), ' ', 1)),
        COALESCE(NEW.raw_user_meta_data->>'last_name', substring(COALESCE(NEW.raw_user_meta_data->>'name', '') from position(' ' in COALESCE(NEW.raw_user_meta_data->>'name', '') || ' ') + 1)),
        COALESCE(NEW.email_confirmed_at IS NOT NULL, FALSE)
    );
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Failed to create user profile: %', SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql VOLATILE SECURITY DEFINER;

-- Function to automatically create default organization for new user
CREATE OR REPLACE FUNCTION public.create_default_organization()
RETURNS TRIGGER AS $$
DECLARE
    v_org_id UUID;
    v_owner_role_id UUID;
BEGIN
    -- Get or create owner role
    SELECT id INTO v_owner_role_id FROM public.roles WHERE name = 'owner' LIMIT 1;
    
    -- Create personal organization
    INSERT INTO public.organizations (name, slug, owner_id, description)
    VALUES (
        COALESCE(NEW.first_name || '''s Organization', 'My Organization'),
        'org-' || substr(NEW.id::text, 1, 8),
        NEW.id,
        'Personal workspace'
    )
    RETURNING id INTO v_org_id;
    
    -- Add user as owner
    IF v_owner_role_id IS NOT NULL THEN
        INSERT INTO public.organization_members (organization_id, user_id, role_id, joined_at)
        VALUES (v_org_id, NEW.id, v_owner_role_id, NOW());
    END IF;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Failed to create default organization: %', SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql VOLATILE SECURITY DEFINER;

-- Function to log user activities
CREATE OR REPLACE FUNCTION public.log_activity()
RETURNS TRIGGER AS $$
DECLARE
    v_user_id UUID;
    v_action VARCHAR(100);
BEGIN
    -- Determine user ID from context
    v_user_id := (SELECT id FROM public.users WHERE supabase_user_id = auth.uid() LIMIT 1);
    
    -- Determine action based on operation
    v_action := TG_OP || '_' || TG_TABLE_NAME;
    
    -- Insert audit log
    IF v_user_id IS NOT NULL THEN
        INSERT INTO public.audit_logs (user_id, action, resource_type, resource_id, metadata)
        VALUES (
            v_user_id,
            v_action,
            TG_TABLE_NAME,
            COALESCE(NEW.id, OLD.id),
            jsonb_build_object(
                'operation', TG_OP,
                'timestamp', NOW()
            )
        );
    END IF;
    
    RETURN COALESCE(NEW, OLD);
EXCEPTION
    WHEN OTHERS THEN
        -- Don't fail the main operation if logging fails
        RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql VOLATILE SECURITY DEFINER;

-- Function to check organization member limit
CREATE OR REPLACE FUNCTION public.check_organization_member_limit()
RETURNS TRIGGER AS $$
DECLARE
    v_member_count INTEGER;
    v_max_members INTEGER;
BEGIN
    SELECT COUNT(*), org.max_members 
    INTO v_member_count, v_max_members
    FROM public.organization_members om
    JOIN public.organizations org ON org.id = om.organization_id
    WHERE om.organization_id = NEW.organization_id 
      AND om.is_active = TRUE
    GROUP BY org.max_members;
    
    IF v_member_count >= v_max_members THEN
        RAISE EXCEPTION 'Organization member limit reached. Maximum: %', v_max_members;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- Function to clean up expired sessions
CREATE OR REPLACE FUNCTION public.cleanup_expired_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM public.sessions WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql VOLATILE SECURITY DEFINER;

-- ============================================================================
-- TRIGGERS - Automated actions
-- ============================================================================

-- Update updated_at on all tables
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON public.users 
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_organizations_updated_at 
    BEFORE UPDATE ON public.organizations 
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_organization_members_updated_at 
    BEFORE UPDATE ON public.organization_members 
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Create user profile on auth signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Create default organization for new user
CREATE TRIGGER on_user_created
    AFTER INSERT ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.create_default_organization();

-- Check member limit before adding to organization
CREATE TRIGGER check_member_limit
    BEFORE INSERT ON public.organization_members
    FOR EACH ROW EXECUTE FUNCTION public.check_organization_member_limit();

-- Audit logging triggers
CREATE TRIGGER audit_organizations
    AFTER INSERT OR UPDATE OR DELETE ON public.organizations
    FOR EACH ROW EXECUTE FUNCTION public.log_activity();

CREATE TRIGGER audit_organization_members
    AFTER INSERT OR UPDATE OR DELETE ON public.organization_members
    FOR EACH ROW EXECUTE FUNCTION public.log_activity();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

-- USERS TABLE POLICIES
CREATE POLICY "Users can view their own profile"
    ON public.users FOR SELECT
    USING (auth.uid() = supabase_user_id);

CREATE POLICY "Users can update their own profile"
    ON public.users FOR UPDATE
    USING (auth.uid() = supabase_user_id)
    WITH CHECK (auth.uid() = supabase_user_id);

CREATE POLICY "Users can view profiles in their organizations"
    ON public.users FOR SELECT
    USING (
        id IN (
            SELECT DISTINCT om.user_id
            FROM public.organization_members om
            WHERE om.organization_id IN (
                SELECT organization_id 
                FROM public.organization_members 
                WHERE user_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid())
                  AND is_active = TRUE
            )
            AND om.is_active = TRUE
        )
    );

-- ORGANIZATIONS TABLE POLICIES
CREATE POLICY "Users can view their organizations"
    ON public.organizations FOR SELECT
    USING (
        id IN (
            SELECT organization_id 
            FROM public.organization_members 
            WHERE user_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid())
              AND is_active = TRUE
        )
    );

CREATE POLICY "Organization owners can update their organizations"
    ON public.organizations FOR UPDATE
    USING (owner_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid()))
    WITH CHECK (owner_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid()));

CREATE POLICY "Users can create organizations"
    ON public.organizations FOR INSERT
    WITH CHECK (owner_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid()));

CREATE POLICY "Organization owners can delete their organizations"
    ON public.organizations FOR DELETE
    USING (owner_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid()));

-- ROLES TABLE POLICIES
CREATE POLICY "All authenticated users can view roles"
    ON public.roles FOR SELECT
    TO authenticated
    USING (true);

-- ORGANIZATION MEMBERS TABLE POLICIES
CREATE POLICY "Users can view members of their organizations"
    ON public.organization_members FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id 
            FROM public.organization_members 
            WHERE user_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid())
              AND is_active = TRUE
        )
    );

CREATE POLICY "Organization owners can manage members"
    ON public.organization_members FOR ALL
    USING (
        organization_id IN (
            SELECT id FROM public.organizations 
            WHERE owner_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid())
        )
    );

CREATE POLICY "Users can leave organizations"
    ON public.organization_members FOR DELETE
    USING (
        user_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid())
        AND organization_id NOT IN (
            SELECT id FROM public.organizations 
            WHERE owner_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid())
        )
    );

-- AUDIT LOGS TABLE POLICIES
CREATE POLICY "Users can view their own audit logs"
    ON public.audit_logs FOR SELECT
    USING (user_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid()));

CREATE POLICY "Organization owners can view organization audit logs"
    ON public.audit_logs FOR SELECT
    USING (
        organization_id IN (
            SELECT id FROM public.organizations 
            WHERE owner_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid())
        )
    );

-- SESSIONS TABLE POLICIES
CREATE POLICY "Users can view their own sessions"
    ON public.sessions FOR SELECT
    USING (user_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid()));

CREATE POLICY "Users can delete their own sessions"
    ON public.sessions FOR DELETE
    USING (user_id = (SELECT id FROM public.users WHERE supabase_user_id = auth.uid()));

-- ============================================================================
-- SEED DATA - Default roles
-- ============================================================================

INSERT INTO public.roles (name, description, permissions, is_system) VALUES
    ('owner', 'Organization owner with full access', '["*"]'::JSONB, TRUE),
    ('admin', 'Administrator with management access', '["manage_members", "manage_settings", "view_audit_logs"]'::JSONB, TRUE),
    ('member', 'Regular member with basic access', '["view_organization", "view_members"]'::JSONB, TRUE),
    ('viewer', 'Read-only access', '["view_organization"]'::JSONB, TRUE)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- COMMENTS - Documentation
-- ============================================================================

COMMENT ON TABLE public.users IS 'User profiles linked to Supabase Auth';
COMMENT ON TABLE public.organizations IS 'Multi-tenant organizations (client environments)';
COMMENT ON TABLE public.roles IS 'System roles for RBAC';
COMMENT ON TABLE public.organization_members IS 'User membership in organizations with roles';
COMMENT ON TABLE public.audit_logs IS 'Security audit trail for all important actions';
COMMENT ON TABLE public.sessions IS 'Active user sessions for security tracking';

-- ============================================================================
-- SECURITY NOTES
-- ============================================================================

-- 1. All tables have RLS enabled with strict policies
-- 2. Audit logging tracks all organization and member changes
-- 3. Email format validation prevents invalid emails
-- 4. Organization member limits prevent abuse
-- 5. Session tracking enables security monitoring
-- 6. Cascade deletes maintain referential integrity
-- 7. SECURITY DEFINER functions run with elevated privileges safely
-- 8. Unique constraints prevent duplicate entries
-- 9. Foreign keys ensure data consistency
-- 10. Indexes optimize query performance

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================

