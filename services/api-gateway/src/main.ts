import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';
import helmet from 'helmet';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.use(helmet());
  app.enableCors({
    origin: [
      process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000',
      process.env.NEXT_PUBLIC_DASHBOARD_URL ?? 'http://localhost:3001',
      process.env.NEXT_PUBLIC_ADMIN_URL ?? 'http://localhost:3002',
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

  const port = process.env.API_GATEWAY_PORT ?? 4000;
  await app.listen(port);
  console.log(`API Gateway running on port ${port}`);
}

bootstrap();
