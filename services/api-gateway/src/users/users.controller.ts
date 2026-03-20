import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Body,
  Param,
  UseGuards,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import { UsersService } from './users.service';

@Controller('users')
@UseGuards(JwtAuthGuard)
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Get('me')
  getProfile(@CurrentUser() user: any) {
    return this.usersService.getProfile(user.id);
  }

  @Put('me')
  updateProfile(
    @CurrentUser() user: any,
    @Body() body: { name?: string; phone?: string; address?: string; city?: string; region?: string },
  ) {
    return this.usersService.updateProfile(user.id, body);
  }

  @Post('push-token')
  updatePushToken(
    @CurrentUser() user: any,
    @Body('pushToken') pushToken: string,
  ) {
    return this.usersService.updatePushToken(user.id, pushToken);
  }

  @Get('price-alerts')
  getPriceAlerts(@CurrentUser() user: any) {
    return this.usersService.getPriceAlerts(user.id);
  }

  @Post('price-alerts')
  createPriceAlert(
    @CurrentUser() user: any,
    @Body() body: { medicationId: string; targetPrice: number; pharmacyId?: string },
  ) {
    return this.usersService.createPriceAlert(user.id, body);
  }

  @Delete('price-alerts/:id')
  deletePriceAlert(@CurrentUser() user: any, @Param('id') alertId: string) {
    return this.usersService.deletePriceAlert(user.id, alertId);
  }
}
