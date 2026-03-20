import { Controller, Get, Param, NotFoundException } from '@nestjs/common';
import { PharmaciesService } from './pharmacies.service';

@Controller('pharmacies')
export class PharmaciesController {
  constructor(private readonly pharmaciesService: PharmaciesService) {}

  @Get()
  async list() {
    return this.pharmaciesService.listActive();
  }

  @Get(':id')
  async getById(@Param('id') id: string) {
    const pharmacy = await this.pharmaciesService.getById(id);
    if (!pharmacy) throw new NotFoundException('Farmacia no encontrada');
    return pharmacy;
  }
}
