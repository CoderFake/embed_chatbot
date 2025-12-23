interface AxiosError {
  response?: {
    data?: {
      detail?: string | Array<{ msg: string }>;
    };
    status?: number;
  };
}

// Map common backend errors to translation keys
const ERROR_MAPPINGS: Record<string, string> = {
  'Invalid credentials': 'errors.invalidCredentials',
  'User not found': 'errors.userNotFound',
  'Email already exists': 'errors.emailExists',
  'User with this email already exists': 'errors.emailExists',
  'Invalid or expired token': 'errors.invalidToken',
  'Token has expired': 'errors.tokenExpired',
  'Invalid email or password': 'errors.invalidCredentials',
  'Incorrect password': 'errors.incorrectPassword',
  'Current password is incorrect': 'errors.incorrectPassword',
  'Passwords do not match': 'errors.passwordMismatch',
  'Password must be at least 8 characters': 'errors.passwordTooShort',
  'Invite not found': 'errors.inviteNotFound',
  'Invite has expired': 'errors.inviteExpired',
  'Invalid or expired reset link': 'errors.invalidResetLink',
}

export function getErrorMessage(
  error: unknown,
  defaultMessage = 'An error occurred',
  translate?: (key: string) => string
): string {
  if (!error) return defaultMessage;

  let errorDetail = '';

  if (typeof error === 'object' && 'response' in error) {
    const axiosError = error as AxiosError;
    const detail = axiosError.response?.data?.detail;

    if (typeof detail === 'string') {
      errorDetail = detail;
    } else if (Array.isArray(detail)) {
      errorDetail = detail.map((e) => e.msg).join(', ');
    }
  } else if (error instanceof Error) {
    errorDetail = error.message;
  }

  // Try to map to translation key
  if (errorDetail && translate) {
    const translationKey = ERROR_MAPPINGS[errorDetail];
    if (translationKey) {
      return translate(translationKey);
    }
  }

  return errorDetail || defaultMessage;
}
