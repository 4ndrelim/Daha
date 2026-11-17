/** Placeholder for domains without an in-browser mock yet. B1 adds real mocks for C's domains. */
export function notMocked<T>(name: string): Promise<T> {
  return Promise.reject(new Error(`mock not implemented: ${name}`));
}
