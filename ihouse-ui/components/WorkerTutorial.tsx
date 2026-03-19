'use client';

import { useState, useEffect } from 'react';
import { useLanguage } from '@/lib/LanguageContext';

export default function WorkerTutorial() {
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState(0);
  const { t } = useLanguage();

  useEffect(() => {
    // Only show to workers (role=worker, ops, cleaner, maintenance, checkin, checkout)
    const role = localStorage.getItem('domaniqo_role') || '';
    const isWorker = ['worker', 'ops', 'cleaner', 'maintenance', 'checkin', 'checkout'].includes(role.toLowerCase());
    
    if (isWorker) {
      const seen = localStorage.getItem('domaniqo_tutorial_seen');
      if (!seen) {
        setIsOpen(true);
      }
    }
  }, []);

  if (!isOpen) return null;

  const slides = [
    {
      title: t('tutorial.welcome_title'),
      content: t('tutorial.welcome_content'),
      icon: '✨'
    },
    {
      title: t('tutorial.tasks_title'),
      content: t('tutorial.tasks_content'),
      icon: '📋'
    },
    {
      title: t('tutorial.ack_title'),
      content: t('tutorial.ack_content'),
      icon: '⏱️'
    },
    {
      title: t('tutorial.report_title'),
      content: t('tutorial.report_content'),
      icon: '⚠️'
    },
    {
      title: t('tutorial.ready_title'),
      content: t('tutorial.ready_content'),
      icon: '🚀'
    }
  ];

  const handleNext = () => {
    if (step < slides.length - 1) {
      setStep(step + 1);
    } else {
      handleClose();
    }
  };

  const handleClose = () => {
    localStorage.setItem('domaniqo_tutorial_seen', 'true');
    setIsOpen(false);
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(0,0,0,0.8)', zIndex: 9999,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 'var(--space-4)'
    }}>
      <div style={{
        background: 'var(--color-surface)',
        borderRadius: 'var(--radius-lg)',
        width: '100%', maxWidth: 400,
        padding: 'var(--space-6)',
        boxShadow: '0 20px 40px rgba(0,0,0,0.4)'
      }}>
        <div style={{ fontSize: 48, textAlign: 'center', marginBottom: 'var(--space-4)' }}>
          {slides[step].icon}
        </div>
        <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, margin: '0 0 var(--space-3) 0', textAlign: 'center' }}>
          {slides[step].title}
        </h2>
        <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-md)', lineHeight: 1.5, textAlign: 'center', margin: '0 0 var(--space-6) 0' }}>
          {slides[step].content}
        </p>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 6 }}>
            {slides.map((_, i) => (
              <div key={i} style={{
                width: i === step ? 24 : 8, height: 8,
                borderRadius: 4,
                background: i === step ? 'var(--color-primary)' : 'var(--color-border)',
                transition: 'all 0.3s'
              }} />
            ))}
          </div>
          
          <button 
            onClick={handleNext}
            style={{
              padding: '10px 24px', background: 'var(--color-primary)', color: '#fff',
              border: 'none', borderRadius: 'var(--radius-md)', fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            {step === slides.length - 1 ? t('tutorial.start') : t('tutorial.next')}
          </button>
        </div>
      </div>
    </div>
  );
}
