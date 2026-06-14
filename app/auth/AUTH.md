For a team of 4 developers, split the authentication service by responsibility rather than by endpoints. This reduces merge conflicts and allows parallel development.
Authentication Service Structure
auth/
├── api/
│   ├── auth_routes.py
│   └── oauth_routes.py
│
├── services/
│   ├── auth_service.py
│   ├── token_service.py
│   ├── otp_service.py
│   ├── password_reset_service.py
│   └── oauth_service.py
│
├── models/
│   ├── user.py
│   ├── refresh_token.py
│   └── otp.py
│
├── schemas/
│   ├── auth.py
│   ├── otp.py
│   └── password_reset.py
│
├── repositories/
│   ├── user_repository.py
│   ├── token_repository.py
│   └── otp_repository.py
│
├── security/
│   ├── jwt.py
│   ├── password.py
│   ├── roles.py
│   └── dependencies.py
│
├── utils/
│   ├── email.py
│   └── validators.py
│
└── tests/
    ├── test_auth.py
    ├── test_oauth.py
    └── test_otp.py


Person 1 — Registration & Login
Responsibility
Core authentication flow.
APIs
POST /auth/register
POST /auth/login
POST /auth/logout

Files
api/auth_routes.py
services/auth_service.py
repositories/user_repository.py
models/user.py
schemas/auth.py
security/password.py

Tasks
User registration
Password hashing (bcrypt)
Email validation
Institutional domain restriction
Login verification
Account status check
Logout endpoint
Redis session invalidation

Person 2 — JWT & Session Management
Responsibility
Token generation, validation, refresh rotation.
APIs
POST /auth/refresh

Files
security/jwt.py
services/token_service.py
repositories/token_repository.py
models/refresh_token.py
security/dependencies.py

Tasks
Create Access Token (30 min)
Create Refresh Token (7 days)
JWT verification
Token rotation
Refresh token revocation
Cookie handling
Authentication middleware
Rate limiting for /refresh endpoint
JWT Payload
{
  "sub": "user-id",
  "email": "user@cet.ac.in",
  "role": "user",
  "status": "active",
  "exp": 1234567890
}

Since role is inside JWT:
if payload["role"] == "admin":
    ...

No RBAC database lookup required for every request.

Person 3 — Google OAuth
Responsibility
Institutional SSO.
APIs
GET /auth/google
GET /auth/google/callback

Files
api/oauth_routes.py
services/oauth_service.py
security/jwt.py
repositories/user_repository.py

Tasks
Google OAuth setup
State verification
Exchange authorization code
Fetch user profile
Check @tkmce.ac.in domain
Auto-create institutional users
Issue JWT pair
Set refresh cookie

Person 4 — OTP & Password Recovery
Responsibility
Verification and recovery.
APIs
POST /auth/verify-otp
POST /auth/resend-otp
POST /auth/forgot-password

Files
services/otp_service.py
services/password_reset_service.py
repositories/otp_repository.py
models/otp.py
utils/email.py
schemas/otp.py
schemas/password_reset.py

Tasks
Generate 6-digit OTP
Store OTP in Redis
OTP expiry
OTP validation
Resend OTP
Password reset email
Password reset token generation

Shared Contracts (Decide Before Coding)
All 4 developers should agree on:
User Model
class User:
    id: UUID
    email: str
    full_name: str
    password_hash: str
    role: str
    status: str

Status Values
pending
active
suspended

Roles
user
moderator
admin
super_admin

JWT Claims
{
  "sub": "uuid",
  "email": "user@tkmce.ac.in",
  "role": "user",
  "status": "active"
}



developers work simultaneously
Step 1: Team Meeting (1–2 hours)
Agree on:
User Schema
User {
    id: UUID
    email: str
    full_name: str
    password_hash: str
    role: str
    status: str
}

JWT Payload
{
  "sub": "user_id",
  "email": "user@tkmce.ac.in",
  "role": "user",
  "status": "active"
}

Database Tables
users
refresh_tokens
otp_codes

API Contracts
Example:
POST /auth/login

returns
{
  "access_token": "...",
  "token_type": "bearer",
  "user": {}
}

Once everyone agrees, they can work independently.

Person 1: Registration/Login
Works on:
auth_service.py
user_repository.py

Can initially fake JWT generation:
return {
    "access_token": "dummy-token"
}

No need to wait for Person 2.

Person 2: JWT/Refresh Tokens
Works on:
jwt.py
token_service.py

Creates:
create_access_token()
create_refresh_token()
verify_token()

Tests using hardcoded users:
payload = {
    "sub": "123",
    "role": "user"
}

No need for registration or database.

Person 3: Google OAuth
Works on:
oauth_service.py
oauth_routes.py

Can use mocked user creation:
user = {
    "email": "test@tkmce.ac.in"
}

Later replace with actual repository.
No dependency on login flow.

Person 4: OTP & Password Reset
Works on:
otp_service.py
password_reset_service.py

Tests:
generate_otp()
verify_otp()

using Redis or in-memory storage.
No dependency on OAuth or JWT.

How Integration Happens
Suppose Person 1 wrote:
def login(email, password):
    ...

and Person 2 wrote:
def create_access_token(user):
    ...

During integration:
def login(email, password):

    user = verify_credentials(email, password)

    access_token = create_access_token(user)

    refresh_token = create_refresh_token(user)

    return {
        "access_token": access_token
    }

Only a few lines need connecting.

Typical Git Workflow
Everyone works on their own branch:
git checkout -b feature/login
git checkout -b feature/jwt
git checkout -b feature/oauth
git checkout -b feature/otp

Then:
feature/login
      \
feature/jwt
        \
feature/oauth
          \
feature/otp
             \
              develop

Merge into develop through pull requests.

For a Student Project
I would divide it like this:
Developer
Responsibility
Dev 1
Register, Login, Logout
Dev 2
JWT, Refresh Tokens, RBAC Middleware
Dev 3
Google OAuth SSO
Dev 4
OTP, Forgot Password, Email Service

The only thing everyone must agree on beforehand is:
User model
JWT payload structure
Database schema
API request/response formats
After that, all four can work simultaneously with minimal blocking.
