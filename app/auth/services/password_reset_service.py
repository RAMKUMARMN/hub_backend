"""
Password reset service — email-based password recovery flow.

Person 4 (OTP & Password Recovery) owns this file.
Depends on: repositories/user_repository.py, security/jwt.py (for reset token), utils/email.py

TODO:
  1. send_reset_email(email) → None
       - Look up user by email (silently ignore unknown addresses).
       - Generate a short-lived password-reset token (JWT or random token).
       - Email the token link to the user via utils/email.py.

  2. reset_password(token, new_password) → None
       - Validate the reset token (expiry + single-use).
       - Hash the new password (security/password.py).
       - Update user.hashed_password via UserRepository.
       - Invalidate the token.
"""
