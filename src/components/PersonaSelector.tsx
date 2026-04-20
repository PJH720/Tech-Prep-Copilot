import React, { useEffect, useState } from 'react';
import { cn } from '../lib/utils';
import { Loader2 } from 'lucide-react';

export interface PersonaInfo {
  id: string;
  emoji: string;
  name: string;
  summary: string;
  interview_character: string;
  feedback_character: string;
}

interface PersonaSelectorProps {
  selectedPersonaId: string;
  onSelect: (id: string) => void;
  onPersonasLoaded?: (personas: PersonaInfo[]) => void;
  disabled?: boolean;
}

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export const PERSONAS: PersonaInfo[] = [
  {
    id: 'dual-strict',
    emoji: '🧊',
    name: '나엄격 / 나친절',
    summary: '두 면접관이 질문·피드백을 랜덤으로 번갈아 진행 — 압박 기술 검증 + 성장 방향 코칭',
    interview_character: '나엄격 (42세, 테크 리드)',
    feedback_character: '나친절 (32세, 시니어 개발자)',
  },
  {
    id: 'business-roi',
    emoji: '📈',
    name: '마계산 / 오네트',
    summary: '두 면접관이 질문·피드백을 랜덤으로 번갈아 진행 — ROI 임팩트 검증 + 비즈니스 확장 시각',
    interview_character: '마계산 (45세, 사업전략 본부장)',
    feedback_character: '오네트 (35세, 창업가 출신 PM)',
  },
  {
    id: 'infra-scale',
    emoji: '🏗️',
    name: '권스케일 / 이안정',
    summary: '두 면접관이 질문·피드백을 랜덤으로 번갈아 진행 — 대규모 확장성 검증 + SRE 실무 멘토링',
    interview_character: '권스케일 (45세, 인프라/SRE 아키텍트)',
    feedback_character: '이안정 (38세, 시니어 SRE 엔지니어)',
  },
  {
    id: 'algo-global',
    emoji: '💻',
    name: '박알고 / 최코치',
    summary: '두 면접관이 질문·피드백을 랜덤으로 번갈아 진행 — FAANG식 알고리즘 압박 + CS 기초 코칭',
    interview_character: '박알고 (38세, FAANG 출신 테크 인터뷰어)',
    feedback_character: '최코치 (33세, 코딩 인터뷰 코치)',
  },
];

export const PersonaSelector: React.FC<PersonaSelectorProps> = ({
  selectedPersonaId,
  onSelect,
  onPersonasLoaded,
  disabled = false,
}) => {
  const [personas, setPersonas] = useState<PersonaInfo[]>(PERSONAS);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/personas`)
      .then((r) => r.json())
      .then((data) => {
        const loaded = data.personas ?? PERSONAS;
        setPersonas(loaded);
        onPersonasLoaded?.(loaded);
      })
      .catch(() => {
        setPersonas(PERSONAS);
        onPersonasLoaded?.(PERSONAS);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
        <Loader2 className="w-4 h-4 animate-spin" />
        면접관 불러오는 중...
      </div>
    );
  }

  return (
    <div className="space-y-2 w-full">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        면접관 페르소나 선택
      </p>
      <div className="grid grid-cols-2 gap-2">
        {personas.map((p) => {
          const isSelected = selectedPersonaId === p.id;
          return (
            <button
              key={p.id}
              onClick={() => !disabled && onSelect(p.id)}
              disabled={disabled}
              className={cn(
                'p-3 rounded-xl border text-left transition-all duration-150',
                isSelected
                  ? 'border-primary bg-primary/5 shadow-sm'
                  : 'border-border hover:border-primary/40 hover:bg-muted/30',
                disabled && 'opacity-50 cursor-not-allowed'
              )}
            >
              {/* 헤더: 이모지 + 타입명 */}
              <div className="flex items-center gap-1.5">
                <span className="text-lg leading-none">{p.emoji}</span>
                <span className="text-xs font-bold text-foreground">{p.name}</span>
              </div>

              {/* 한줄 설명 */}
              <p className="text-[10px] text-muted-foreground mt-1.5 leading-snug">
                {p.summary}
              </p>

              {/* 구분선 */}
              <div className="border-t border-border/50 my-2" />

              {/* 두 면접관 */}
              <div className="space-y-1">
                <div className="flex items-start gap-1.5">
                  <span className="text-[10px] font-semibold text-primary shrink-0 mt-px">👤 면접관 A</span>
                  <span className="text-[10px] text-foreground leading-snug">{p.interview_character}</span>
                </div>
                <div className="flex items-start gap-1.5">
                  <span className="text-[10px] font-semibold text-primary shrink-0 mt-px">👤 면접관 B</span>
                  <span className="text-[10px] text-foreground leading-snug">{p.feedback_character}</span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
