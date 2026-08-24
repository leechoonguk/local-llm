export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = "ApiError"
  }

  static fromResponse(res: Response): ApiError {
    return new ApiError(res.status, `HTTP ${res.status}`)
  }
}
