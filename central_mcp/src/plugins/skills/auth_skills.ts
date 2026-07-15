import { SmartHubSkill } from '../../types/index.js';
import { createJsonSkill, stringProperty } from './skill_helpers.js';

export const authSkills: SmartHubSkill[] = [
    createJsonSkill({
        name: 'login_to_gateway',
        description: 'Authenticate with email and password and request a login OTP.',
        method: 'POST',
        endpoint: '/api/v1/auth/login',
        requiresAuth: false,
        schema: {
            type: 'object',
            properties: {
                email: stringProperty('Account email.', 'email'),
                password: stringProperty('Account password.'),
            },
            required: ['email', 'password'],
            additionalProperties: false,
        },
        body: args => ({ email: args.email, password: args.password }),
    }),
    createJsonSkill({
        name: 'verify_otp',
        description: 'Verify the phone OTP and return access and refresh tokens.',
        method: 'POST',
        endpoint: '/api/v1/auth/verify-otp',
        requiresAuth: false,
        schema: {
            type: 'object',
            properties: {
                phone: stringProperty('Phone number returned by login.'),
                otp: stringProperty('Login OTP.'),
            },
            required: ['phone', 'otp'],
            additionalProperties: false,
        },
        body: args => ({ phone: args.phone, otp: args.otp }),
    }),
    createJsonSkill({
        name: 'forgot_password',
        description: 'Request a password reset code for an email address.',
        method: 'POST',
        endpoint: '/api/v1/auth/forgot-password',
        requiresAuth: false,
        schema: {
            type: 'object',
            properties: { email: stringProperty('Account email.', 'email') },
            required: ['email'],
            additionalProperties: false,
        },
        body: args => ({ email: args.email }),
    }),
    createJsonSkill({
        name: 'reset_password',
        description: 'Reset a password using the recovery code.',
        method: 'POST',
        endpoint: '/api/v1/auth/reset-password',
        requiresAuth: false,
        schema: {
            type: 'object',
            properties: {
                email: stringProperty('Account email.', 'email'),
                code: stringProperty('Password reset code.'),
                new_password: stringProperty('New account password.'),
            },
            required: ['email', 'code', 'new_password'],
            additionalProperties: false,
        },
        body: args => ({ email: args.email, code: args.code, new_password: args.new_password }),
    }),
    createJsonSkill({
        name: 'refresh_access_token',
        description: 'Exchange a refresh token for a new access and refresh token pair.',
        method: 'POST',
        endpoint: '/api/v1/auth/refresh',
        requiresAuth: false,
        schema: {
            type: 'object',
            properties: { refresh_token: stringProperty('Refresh token.') },
            required: ['refresh_token'],
            additionalProperties: false,
        },
        body: args => ({ refresh_token: args.refresh_token }),
    }),
    createJsonSkill({
        name: 'logout_from_gateway',
        description: 'Log out the authenticated user.',
        method: 'POST',
        endpoint: '/api/v1/auth/logout',
    }),
];
