import React from 'react';
import { Building2, Check } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { useAppStore } from '../lib/store';
import { CompanyInfo } from '../types';
import { cn } from '../lib/utils';

const COMPANIES: CompanyInfo[] = [
  {
    id: 'kakao',
    name: 'Kakao',
    logo: 'https://picsum.photos/seed/kakao/100/100',
    description: 'South Korean internet company offering messaging, commerce, and financial services.',
    techBlogUrl: 'https://tech.kakao.com',
    recentTechStack: ['Kotlin', 'Spring Boot', 'Kubernetes', 'React', 'TypeScript', 'Kafka'],
  },
  {
    id: 'naver',
    name: 'Naver',
    logo: 'https://picsum.photos/seed/naver/100/100',
    description: 'Leading search engine and IT platform in South Korea.',
    techBlogUrl: 'https://d2.naver.com',
    recentTechStack: ['Java', 'Spring Cloud', 'Redis', 'Vue.js', 'MySQL', 'Hadoop'],
  },
  {
    id: 'toss',
    name: 'Toss (Viva Republica)',
    logo: 'https://picsum.photos/seed/toss/100/100',
    description: 'Fintech unicorn providing a wide range of financial services through its super app.',
    techBlogUrl: 'https://toss.tech',
    recentTechStack: ['Node.js', 'TypeScript', 'React Native', 'PostgreSQL', 'AWS', 'Terraform'],
  },
  {
    id: 'coupang',
    name: 'Coupang',
    logo: 'https://picsum.photos/seed/coupang/100/100',
    description: 'E-commerce giant known for its Rocket Delivery service.',
    techBlogUrl: 'https://medium.com/coupang-engineering',
    recentTechStack: ['Java', 'Python', 'Go', 'Spark', 'Cassandra', 'Microservices'],
  },
];

export const CompanySelector: React.FC = () => {
  const { selectedCompany, setSelectedCompany } = useAppStore();

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="w-5 h-5 text-primary" />
          Target Company
        </CardTitle>
        <CardDescription>
          Select the company you want to prepare for.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {COMPANIES.map((company) => (
            <button
              key={company.id}
              onClick={() => setSelectedCompany(company)}
              className={cn(
                "flex items-center gap-4 p-4 rounded-xl border-2 text-left transition-all hover:border-primary/50",
                selectedCompany?.id === company.id 
                  ? "border-primary bg-primary/5 ring-2 ring-primary/20" 
                  : "border-muted bg-card"
              )}
            >
              <img 
                src={company.logo} 
                alt={company.name} 
                className="w-12 h-12 rounded-lg object-cover"
                referrerPolicy="no-referrer"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold truncate">{company.name}</h3>
                  {selectedCompany?.id === company.id && (
                    <Check className="w-4 h-4 text-primary shrink-0" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground line-clamp-1">
                  {company.techBlogUrl}
                </p>
              </div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
