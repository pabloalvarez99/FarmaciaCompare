import { Injectable, BadRequestException } from '@nestjs/common';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { prisma } from '@farmacia/database';
import { ConfigService } from '@nestjs/config';
import { v4 as uuidv4 } from 'uuid';
import * as path from 'path';

@Injectable()
export class PrescriptionsService {
  private s3: S3Client;
  private bucket: string;
  private endpoint: string;

  constructor(private configService: ConfigService) {
    this.endpoint = configService.get('S3_ENDPOINT', 'http://localhost:9000');
    this.bucket = configService.get('S3_BUCKET', 'farmacia-uploads');

    this.s3 = new S3Client({
      region: configService.get('AWS_REGION', 'us-east-1'),
      endpoint: this.endpoint,
      forcePathStyle: true,
      credentials: {
        accessKeyId: configService.get('S3_ACCESS_KEY', ''),
        secretAccessKey: configService.get('S3_SECRET_KEY', ''),
      },
    });
  }

  async upload(userId: string, file: Express.Multer.File, orderId?: string) {
    const ext = path.extname(file.originalname);
    const key = `prescriptions/${userId}/${uuidv4()}${ext}`;

    await this.s3.send(
      new PutObjectCommand({
        Bucket: this.bucket,
        Key: key,
        Body: file.buffer,
        ContentType: file.mimetype,
      }),
    );

    const fileUrl = `${this.endpoint}/${this.bucket}/${key}`;

    return prisma.prescription.create({
      data: {
        id: uuidv4(),
        userId,
        orderId: orderId ?? null,
        fileUrl,
        status: 'pending',
      },
    });
  }

  async findAllForUser(userId: string) {
    return prisma.prescription.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
    });
  }
}
