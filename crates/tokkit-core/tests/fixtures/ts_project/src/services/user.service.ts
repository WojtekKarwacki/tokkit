import { User } from '../types';

export class UserService {
    getUser(id: number): User {
        return { id, name: 'Alice', email: 'alice@example.com' };
    }

    createUser(name: string, email: string): User {
        return { id: 1, name, email };
    }
}
