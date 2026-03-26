import { Module } from '@nestjs/common';
import { MedicationsController } from './medications.controller';
import { MedicationsService } from './medications.service';
import { PriceServiceClient } from './price-service.client';

@Module({
  controllers: [MedicationsController],
  providers: [MedicationsService, PriceServiceClient],
  exports: [MedicationsService],
})
export class MedicationsModule {}
