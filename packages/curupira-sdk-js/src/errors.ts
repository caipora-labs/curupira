/** Raised when a trigger cannot be registered. */
export class RegistrationError extends Error {
  override readonly name = "RegistrationError";
}

/** Raised when a return value cannot be converted to protocol pairs. */
export class SerializationError extends Error {
  override readonly name = "SerializationError";
}

/** Raised when automation configuration fails validation. */
export class ValidationError extends Error {
  override readonly name = "ValidationError";
}

/** JSON-RPC error with a protocol error code. */
export class RpcError extends Error {
  override readonly name = "RpcError";
  readonly code: number;
  readonly data?: unknown;

  constructor(code: number, message: string, data?: unknown) {
    super(message);
    this.code = code;
    if (data !== undefined) {
      this.data = data;
    }
  }
}
