"""
OAuth tests — Person 3 writes here.

TODO:
  - test_google_login_redirects: GET /auth/google → 302 with location header
  - test_google_callback_valid_domain: valid @tkmce.ac.in email → 200 + tokens
  - test_google_callback_invalid_domain: @gmail.com → 403
  - test_google_callback_invalid_state: tampered state → 400
"""
