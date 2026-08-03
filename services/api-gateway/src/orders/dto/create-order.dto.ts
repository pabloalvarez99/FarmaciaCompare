import { IsUUID, IsEnum, IsArray, ValidateNested, IsInt, Min, IsOptional, IsString } from 'class-validator';
import { Type } from 'class-transformer';

class OrderItemDto {
  @IsUUID() declare pharmacyProductId: string;
  @IsInt() @Min(1) declare quantity: number;
}

export class CreateOrderDto {
  @IsUUID() declare pharmacyId: string;
  @IsEnum(['delivery', 'pickup']) declare type: 'delivery' | 'pickup';
  @IsArray() @ValidateNested({ each: true }) @Type(() => OrderItemDto) declare items: OrderItemDto[];
  @IsOptional() @IsString() deliveryAddress?: string;
  @IsOptional() @IsString() notes?: string;
}
