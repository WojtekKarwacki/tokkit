export interface User {
    id: number;
    name: string;
    email: string;
}

export interface AuthToken {
    token: string;
    expiresAt: number;
}

export enum UserRole {
    Admin,
    Editor,
    Viewer,
// rev-4
// rev-7
}
