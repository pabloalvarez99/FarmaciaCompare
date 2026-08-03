import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';
import helmet from 'helmet';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.use(helmet());

  // CORS_ORIGINS carries the deployed frontends (Vercel gives each project its
  // own domain, so the list cannot be hardcoded).
  const extraOrigins = (process.env.CORS_ORIGINS ?? '')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);

  app.enableCors({
    origin: [
      process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000',
      process.env.NEXT_PUBLIC_DASHBOARD_URL ?? 'http://localhost:3001',
      process.env.NEXT_PUBLIC_ADMIN_URL ?? 'http://localhost:3002',
      ...extraOrigins,
    ],
    credentials: true,
  });

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  app.setGlobalPrefix('api/v1');

  // Cloud Run injects PORT and requires binding on 0.0.0.0.
  const port = process.env.PORT ?? process.env.API_GATEWAY_PORT ?? 4000;
  await app.listen(port, '0.0.0.0');
  console.log(`API Gateway running on port ${port}`);
}

bootstrap();
