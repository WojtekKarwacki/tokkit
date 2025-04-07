import { AuthToken } from '../types';
import { hashPassword } from '../utils/helpers';

export class AuthService {
    authenticate(username: string, password: string): AuthToken {
        const hashed = hashPassword(password);
        return { token: 'abc', expiresAt: Date.now() + 3600 };
    }

    validateToken(token: string): boolean {
        return token.length > 0;
    }
}
