import { Injectable, LoggerService as NestLoggerService } from '@nestjs/common';

@Injectable()
export class StructuredLogger implements NestLoggerService {
  log(message: any, context?: string) {
    process.stdout.write(
      JSON.stringify({
        level: 'info',
        message,
        context,
        timestamp: new Date().toISOString(),
      }) + '\n',
    );
  }

  error(message: any, trace?: string, context?: string) {
    process.stderr.write(
      JSON.stringify({
        level: 'error',
        message,
        trace,
        context,
        timestamp: new Date().toISOString(),
      }) + '\n',
    );
  }

  warn(message: any, context?: string) {
    process.stdout.write(
      JSON.stringify({
        level: 'warn',
        message,
        context,
        timestamp: new Date().toISOString(),
      }) + '\n',
    );
  }

  debug(message: any, context?: string) {
    if (process.env.NODE_ENV !== 'production') {
      process.stdout.write(
        JSON.stringify({
          level: 'debug',
          message,
          context,
          timestamp: new Date().toISOString(),
        }) + '\n',
      );
    }
  }

  verbose(message: any, context?: string) {
    if (process.env.NODE_ENV !== 'production') {
      process.stdout.write(
        JSON.stringify({
          level: 'verbose',
          message,
          context,
          timestamp: new Date().toISOString(),
        }) + '\n',
      );
    }
  }
}
