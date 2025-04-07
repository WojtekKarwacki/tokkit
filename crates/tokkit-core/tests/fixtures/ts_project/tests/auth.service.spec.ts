import { AuthService } from '../src/services/auth.service';

function testAuthenticate() {
    const svc = new AuthService();
    const token = svc.authenticate('admin', 'password');
}
