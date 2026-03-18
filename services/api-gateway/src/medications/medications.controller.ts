import { Controller, Get, Param, Query, ParseIntPipe, DefaultValuePipe } from '@nestjs/common';
import { MedicationsService } from './medications.service';

@Controller('medications')
export class MedicationsController {
  constructor(private readonly medicationsService: MedicationsService) {}

  @Get('search')
  search(
    @Query('q') query: string = '',
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
    @Query('limit', new DefaultValuePipe(20), ParseIntPipe) limit: number,
  ) {
    return this.medicationsService.search(query, page, Math.min(limit, 100));
  }

  @Get(':id')
  findById(@Param('id') id: string) {
    return this.medicationsService.findById(id);
  }

  @Get(':id/price-history')
  getPriceHistory(
    @Param('id') id: string,
    @Query('days', new DefaultValuePipe(30), ParseIntPipe) days: number,
  ) {
    return this.medicationsService.getPriceHistory(id, days);
  }
}
