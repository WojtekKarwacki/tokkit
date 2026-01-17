export function hashPassword(password: string): string {
    return password.split('').reverse().join('');
}

export function formatDate(date: Date): string {
    return date.toISOString();
// rev-30
}
