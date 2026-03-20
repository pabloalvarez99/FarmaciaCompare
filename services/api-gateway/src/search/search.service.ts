import { Injectable, OnModuleInit, Logger } from '@nestjs/common';
import { Client } from '@elastic/elasticsearch';
import { ConfigService } from '@nestjs/config';

const INDEX = 'medications';

@Injectable()
export class SearchService implements OnModuleInit {
  private readonly logger = new Logger(SearchService.name);
  private client: Client;

  constructor(private configService: ConfigService) {
    this.client = new Client({
      node: configService.get('ELASTICSEARCH_URL', 'http://localhost:9200'),
    });
  }

  async onModuleInit() {
    try {
      await this.ensureIndex();
    } catch (e) {
      this.logger.warn('Elasticsearch not available, search will fallback to DB');
    }
  }

  async ensureIndex() {
    const exists = await this.client.indices.exists({ index: INDEX });
    if (!exists) {
      await this.client.indices.create({
        index: INDEX,
        mappings: {
          properties: {
            id: { type: 'keyword' },
            name: {
              type: 'text',
              analyzer: 'spanish',
              fields: { keyword: { type: 'keyword' } },
            },
            activeIngredientName: { type: 'text', analyzer: 'spanish' },
            brandNames: { type: 'text', analyzer: 'spanish' },
            dosage: { type: 'keyword' },
            pharmaceuticalForm: { type: 'keyword' },
            prescriptionRequired: { type: 'boolean' },
            lowestPrice: { type: 'integer' },
            pharmacyCount: { type: 'integer' },
          },
        },
        settings: {
          analysis: {
            analyzer: {
              spanish: {
                tokenizer: 'standard',
                filter: ['lowercase', 'asciifolding', 'spanish_stop'],
              },
            },
            filter: {
              spanish_stop: { type: 'stop', stopwords: '_spanish_' },
            },
          },
        },
      });
    }
  }

  async search(query: string, page = 1, limit = 20) {
    const from = (page - 1) * limit;
    const result = await this.client.search({
      index: INDEX,
      from,
      size: limit,
      query: query
        ? {
            multi_match: {
              query,
              fields: ['name^3', 'brandNames^2', 'activeIngredientName^2', 'dosage'],
              fuzziness: 'AUTO',
              type: 'best_fields',
            },
          }
        : { match_all: {} },
    });

    return {
      results: result.hits.hits.map((h) => h._source),
      total:
        typeof result.hits.total === 'number'
          ? result.hits.total
          : result.hits.total?.value ?? 0,
      page,
      limit,
    };
  }

  async indexMedication(medication: {
    id: string;
    name: string;
    activeIngredientName: string;
    brandNames: string[];
    dosage: string;
    pharmaceuticalForm: string;
    prescriptionRequired: boolean;
    lowestPrice: number | null;
    pharmacyCount: number;
  }) {
    await this.client.index({
      index: INDEX,
      id: medication.id,
      document: medication,
    });
  }

  async bulkIndex(medications: any[]) {
    if (!medications.length) return;
    const operations = medications.flatMap((med) => [
      { index: { _index: INDEX, _id: med.id } },
      med,
    ]);
    await this.client.bulk({ operations });
    await this.client.indices.refresh({ index: INDEX });
  }
}
