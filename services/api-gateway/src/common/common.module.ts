import { Module, Global } from '@nestjs/common';
import { StructuredLogger } from './logger.service';
import { MetricsService } from './metrics.service';
import { MetricsController } from './metrics.controller';

@Global()
@Module({
  controllers: [MetricsController],
  providers: [StructuredLogger, MetricsService],
  exports: [StructuredLogger, MetricsService],
})
export class CommonModule {}
