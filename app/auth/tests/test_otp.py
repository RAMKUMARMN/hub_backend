"""
OTP tests — Person 4 writes here.

TODO:
  - test_generate_otp: result is always a 6-digit string
  - test_verify_otp_success: correct code within TTL → True
  - test_verify_otp_expired: code past TTL → False / 400
  - test_verify_otp_wrong_code: wrong code → False / 400
  - test_resend_otp_invalidates_previous: old code rejected after resend
  - test_forgot_password_email_sent: known email → 200 (email sent)
  - test_forgot_password_unknown_email: unknown email → 200 (silent, no leak)
"""
