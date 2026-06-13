"""
OAuth service — Google SSO for institutional (@tkmce.ac.in) accounts.

Person 3 (Google OAuth) owns this file.
Depends on: repositories/user_repository.py, services/token_service.py

TODO:
  1. get_authorization_url(state) → str
       - Build Google OAuth consent URL using google_client_id from settings.

  2. handle_callback(code, state) → TokenResponse
       - Exchange the authorization code for a Google access token.
       - Verify the state parameter to prevent CSRF.
       - Fetch the user profile from Google's userinfo endpoint.
       - Validate that the email ends with @tkmce.ac.in.
       - Upsert the user in the database (auto-create institutional users).
       - Issue a JWT pair via TokenService.issue_pair().
"""
