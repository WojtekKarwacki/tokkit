import { AuthService } from './services/auth.service';
import { UserService } from './services/user.service';

export function bootstrap(): void {
    const auth = new AuthService();
    const users = new UserService();
}
