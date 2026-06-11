"""Users module (Tier-1).

Public surface:
    - api.self_router: GET /users/me, PUT /users/me (self profile).
    - api.admin_router: GET /admin/users (list), POST /admin/users (create),
      PATCH /admin/users/{id}, PATCH /admin/users/{id}/status,
      PATCH /admin/users/{id}/role, POST /admin/users/{id}/reset-password,
      DELETE /admin/users/{id} (gated by Depends(get_current_superuser)).
    - service.UsersService: self-profile builder + field whitelist +
      plan-limits helpers (get_product_limit/get_competitor_limit/is_free_plan).
    - service.UsersAdminService: admin user CRUD with the byte-preserved
      security invariants (no self-deactivate / no last-superuser removal /
      no self-delete / no delete-last-superuser).
    - schemas: UserResponse, UserUpdate, AdminUserCreateRequest,
      AdminUserUpdateRequest, AdminUserStatusRequest, AdminUserRoleRequest,
      AdminUserPasswordResetRequest.

CORE-USERS1 extracted these from core/api_auth.py (/me),
admin/parsing_admin.py + admin/api_parsing.py (admin users), and the orphan
core/plans/service.py (plan-limits delegate).
"""
