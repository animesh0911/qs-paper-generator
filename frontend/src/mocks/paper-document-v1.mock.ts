import type { PaperDocument } from '@/types';

export const mockPaperDocumentV1 = {
  schemaVersion: 'paper_document.v1',
  request: {
    requestId: 'req_mock_cbse_science_001',
    language: 'en',
    classLevel: '10',
    subject: 'Science',
    examType: 'full_term',
    filters: {
      chapters: [
        'Heredity',
        'Life Processes',
        'Electricity',
        'Control and Coordination',
      ],
      topics: ['Monohybrid Cross', 'Transportation', 'Ohm Law', 'Human Brain'],
      englishOnly: true,
      difficultyMix: {
        easy: 25,
        medium: 55,
        hard: 20,
      },
    },
  },
  template: {
    templateId: 'cbse_science_class_10_full_term_v1',
    templateName: 'CBSE Class 10 Science Full Term',
    board: 'CBSE',
    classLevel: '10',
    subject: 'Science',
    examType: 'full_term',
    totalMarks: 80,
    durationMinutes: 180,
    language: 'en',
  },
  format: {
    formatId: 'cbse_science_class_10_v1',
    page: {
      size: 'A4',
      orientation: 'portrait',
    },
    paperChrome: {
      showOuterBorder: true,
      sectionStyle: 'boxed',
      marksPlacement: 'right',
    },
    numbering: {
      scope: 'paper',
      style: 'decimal',
      recomputeOnSectionReorder: true,
    },
    sections: {
      allowQuestionReorderWithinSection: true,
      allowCrossSectionMove: false,
    },
    questionRegions: {
      allowRegionReorder: false,
      allowRegionDelete: false,
    },
    mcqOptions: {
      layout: 'vertical',
    },
  },
  paper: {
    paperId: 'paper_mock_cbse_science_001',
    title: 'Science',
    subtitle: 'Class X',
    totalMarks: 80,
    durationMinutes: 180,
    language: 'en',
    headerBlocks: [
      {
        blockId: 'header_mock_001',
        blockType: 'paper_header',
        text: 'Science - Class X',
        editable: true,
      },
    ],
    instructionBlocks: [
      {
        blockId: 'note_heading',
        blockType: 'note_heading',
        text: 'NOTE',
        editable: true,
      },
      {
        blockId: 'note_printed_pages',
        blockType: 'note',
        text: 'Please check that this question paper contains 31 printed pages.',
        editable: true,
      },
      {
        blockId: 'note_question_count',
        blockType: 'note',
        text: 'Please check that this question paper contains 39 questions.',
        editable: true,
      },
      {
        blockId: 'note_serial_number',
        blockType: 'note',
        text: 'Please write down the Serial Number of the question in the answer-book at the given place before attempting it.',
        editable: true,
      },
      {
        blockId: 'note_reading_time',
        blockType: 'note',
        text: '15 minute time has been allotted to read this question paper. The question paper will be distributed at 10.15 a.m. From 10.15 a.m. to 10.30 a.m., the candidates will read the question paper only and will not write any answer on the answer-book during this period.',
        editable: true,
      },
      {
        blockId: 'general_instructions_heading',
        blockType: 'general_instructions_heading',
        text: 'General Instructions',
        editable: true,
      },
      {
        blockId: 'general_instruction_count',
        blockType: 'general_instruction',
        text: 'This question paper contain 39 questions. All questions are compulsory.',
        editable: true,
      },
      {
        blockId: 'general_instruction_sections',
        blockType: 'general_instruction',
        text: 'The question paper is divided into three sections — A, B and C. Section A: Biology (30 marks), Section B: Chemistry (25 marks), Section C: Physics (25 marks).',
        editable: true,
      },
      {
        blockId: 'general_instruction_types',
        blockType: 'general_instruction',
        text: 'The question paper has MCQs, VSAs, SAs, LAs and CBQs. Marks are given against each question.',
        editable: true,
      },
      {
        blockId: 'general_instruction_cbq',
        blockType: 'general_instruction',
        text: 'There are case based questions (CBQs) with three sub-questions and are of 4 marks each.',
        editable: true,
      },
      {
        blockId: 'general_instruction_answer_sections',
        blockType: 'general_instruction',
        text: 'Divide your answer sheet into three sections as per the question paper — Section A (Biology), Section B (Chemistry) and Section C (Physics). It is compulsory to answer each question in its respective section.',
        editable: true,
      },
      {
        blockId: 'general_instruction_choice',
        blockType: 'general_instruction',
        text: 'There is no overall choice in the question paper. However, an internal choice has been provided in few questions. Only one of the choices in such questions must be attempted.',
        editable: true,
      },
    ],
    sections: [
      {
        sectionId: 'A',
        title: 'Section A',
        subtitle: 'Biology',
        marks: 30,
        instructions:
          'Answer the Biology questions in this section. Instructions are given with each question, wherever necessary.',
        slots: [
          {
            slotId: 'slot_A_01',
            displayNumber: '1',
            marks: 1,
            questionType: 'mcq',
            selectedQuestionId: 'q_mcq_heredity_001',
            locked: false,
            alternateQuestionIds: [
              'q_mcq_heredity_002',
              'q_mcq_electricity_001',
            ],
            overrides: {
              modifiedFromSource: false,
              regions: {},
            },
          },
          {
            slotId: 'slot_A_02',
            displayNumber: '2',
            marks: 1,
            questionType: 'assertion_reason',
            selectedQuestionId: 'q_ar_life_processes_001',
            locked: false,
            alternateQuestionIds: ['q_ar_life_processes_002'],
          },
          {
            slotId: 'slot_B_01',
            displayNumber: '3',
            marks: 2,
            questionType: 'short_answer',
            selectedQuestionId: 'q_short_stomata_001',
            locked: true,
            alternateQuestionIds: ['q_short_stomata_002'],
          },
          {
            slotId: 'slot_C_01',
            displayNumber: '4',
            marks: 5,
            questionType: 'long_answer',
            selectedQuestionId: 'q_long_life_processes_001',
            locked: false,
            alternateQuestionIds: ['q_long_life_processes_002'],
          },
          {
            slotId: 'slot_D_01',
            displayNumber: '5',
            marks: 4,
            questionType: 'case_based',
            selectedQuestionId: 'q_case_brain_001',
            locked: false,
            alternateQuestionIds: ['q_case_brain_002'],
          },
        ],
      },
      {
        sectionId: 'B',
        title: 'Section B',
        subtitle: 'Chemistry',
        marks: 25,
        instructions:
          'Answer the Chemistry questions in this section. Marks are given against each question.',
        slots: [
          {
            slotId: 'slot_E_02',
            displayNumber: '6',
            marks: 5,
            questionType: 'table_based',
            selectedQuestionId: 'q_table_metals_001',
            locked: false,
            alternateQuestionIds: ['q_table_metals_002'],
          },
          {
            slotId: 'slot_C_02',
            displayNumber: '7',
            marks: 5,
            questionType: 'long_answer',
            selectedQuestionId: 'q_long_internal_choice_001',
            locked: false,
            alternateQuestionIds: ['q_long_internal_choice_002'],
            orGroup: 1,
          },
        ],
      },
      {
        sectionId: 'C',
        title: 'Section C',
        subtitle: 'Physics',
        marks: 25,
        instructions:
          'Answer the Physics questions in this section. Internal choice, if any, must be attempted only once.',
        slots: [
          {
            slotId: 'slot_B_02',
            displayNumber: '8',
            marks: 2,
            questionType: 'short_answer',
            selectedQuestionId: 'q_short_electricity_001',
            locked: false,
            alternateQuestionIds: ['q_short_electricity_002'],
          },
          {
            slotId: 'slot_E_01',
            displayNumber: '9',
            marks: 5,
            questionType: 'diagram_based',
            selectedQuestionId: 'q_diagram_electricity_001',
            locked: false,
            alternateQuestionIds: ['q_diagram_electricity_002'],
          },
        ],
      },
    ],
  },
  questions: [
    {
      questionId: 'q_mcq_heredity_001',
      language: 'en',
      marks: 1,
      questionType: 'mcq',
      rawText:
        'What is the phenotypic ratio in the F2 generation of a monohybrid cross?',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'What is the phenotypic ratio in the F2 generation of a monohybrid cross?',
          },
        ],
        options: [
          { label: 'A', content: [{ type: 'paragraph', text: '1 : 1' }] },
          { label: 'B', content: [{ type: 'paragraph', text: '3 : 1' }] },
          { label: 'C', content: [{ type: 'paragraph', text: '1 : 2 : 1' }] },
          {
            label: 'D',
            content: [{ type: 'paragraph', text: '9 : 3 : 3 : 1' }],
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Heredity'],
        topicNames: ['Monohybrid Cross'],
        difficulty: 'medium',
        cognitiveLevel: 'understand',
        cbseRelevance: 'high',
      },
      source: {
        sourceType: 'previous_year_paper',
        sourceName: 'CBSE Science 2024 Set 31/2/1',
        fileName: '31-2-1.pdf',
        pageNumber: 3,
        originalQuestionNumber: '1',
      },
    },
    {
      questionId: 'q_mcq_heredity_002',
      language: 'en',
      marks: 1,
      questionType: 'mcq',
      rawText:
        'Which pair represents contrasting traits studied by Mendel in pea plants?',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'Which pair represents contrasting traits studied by Mendel in pea plants?',
          },
        ],
        options: [
          {
            label: 'A',
            content: [{ type: 'paragraph', text: 'Tall and dwarf' }],
          },
          {
            label: 'B',
            content: [{ type: 'paragraph', text: 'Red and green blood' }],
          },
          {
            label: 'C',
            content: [{ type: 'paragraph', text: 'Metal and non-metal' }],
          },
          {
            label: 'D',
            content: [{ type: 'paragraph', text: 'Acid and base' }],
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Heredity'],
        topicNames: ['Mendel Experiments'],
        difficulty: 'easy',
        cbseRelevance: 'high',
      },
      source: {
        sourceType: 'question_bank',
        sourceName: 'School Science Question Bank',
      },
    },
    {
      questionId: 'q_mcq_electricity_001',
      language: 'en',
      marks: 1,
      questionType: 'mcq',
      rawText: 'Which quantity is measured in ohm?',
      content: {
        stem: [
          { type: 'paragraph', text: 'Which quantity is measured in ohm?' },
        ],
        options: [
          { label: 'A', content: [{ type: 'paragraph', text: 'Current' }] },
          { label: 'B', content: [{ type: 'paragraph', text: 'Resistance' }] },
          {
            label: 'C',
            content: [{ type: 'paragraph', text: 'Potential difference' }],
          },
          { label: 'D', content: [{ type: 'paragraph', text: 'Power' }] },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Physics',
        chapterNames: ['Electricity'],
        topicNames: ['Resistance'],
        difficulty: 'easy',
        cbseRelevance: 'medium',
      },
      source: {
        sourceType: 'question_bank',
        sourceName: 'School Science Question Bank',
      },
    },
    {
      questionId: 'q_ar_life_processes_001',
      language: 'en',
      marks: 1,
      questionType: 'assertion_reason',
      rawText:
        'Assertion (A): Blood plasma transports carbon dioxide. Reason (R): Carbon dioxide is more soluble in water than oxygen.',
      content: {
        assertion: [
          {
            type: 'paragraph',
            text: 'Assertion (A): Blood plasma transports carbon dioxide in dissolved form.',
          },
        ],
        reason: [
          {
            type: 'paragraph',
            text: 'Reason (R): Carbon dioxide is more soluble in water than oxygen.',
          },
        ],
        options: [
          {
            label: 'A',
            content: [
              {
                type: 'paragraph',
                text: 'Both A and R are true and R is the correct explanation of A.',
              },
            ],
          },
          {
            label: 'B',
            content: [
              {
                type: 'paragraph',
                text: 'Both A and R are true but R is not the correct explanation of A.',
              },
            ],
          },
          {
            label: 'C',
            content: [{ type: 'paragraph', text: 'A is true but R is false.' }],
          },
          {
            label: 'D',
            content: [{ type: 'paragraph', text: 'A is false but R is true.' }],
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Life Processes'],
        topicNames: ['Transportation'],
        difficulty: 'medium',
        cognitiveLevel: 'analyse',
        cbseRelevance: 'high',
      },
      source: {
        sourceType: 'previous_year_paper',
        sourceName: 'CBSE Science 2024 Set 31/2/1',
      },
    },
    {
      questionId: 'q_ar_life_processes_002',
      language: 'en',
      marks: 1,
      questionType: 'assertion_reason',
      rawText:
        'Assertion (A): Arteries have thick elastic walls. Reason (R): Blood flows in arteries under high pressure.',
      content: {
        assertion: [
          {
            type: 'paragraph',
            text: 'Assertion (A): Arteries have thick elastic walls.',
          },
        ],
        reason: [
          {
            type: 'paragraph',
            text: 'Reason (R): Blood flows in arteries under high pressure.',
          },
        ],
        options: [
          {
            label: 'A',
            content: [
              {
                type: 'paragraph',
                text: 'Both A and R are true and R is the correct explanation of A.',
              },
            ],
          },
          {
            label: 'B',
            content: [
              {
                type: 'paragraph',
                text: 'Both A and R are true but R is not the correct explanation of A.',
              },
            ],
          },
          {
            label: 'C',
            content: [{ type: 'paragraph', text: 'A is true but R is false.' }],
          },
          {
            label: 'D',
            content: [{ type: 'paragraph', text: 'A is false but R is true.' }],
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Life Processes'],
        topicNames: ['Blood Vessels'],
        difficulty: 'medium',
        cbseRelevance: 'medium',
      },
      source: {
        sourceType: 'question_bank',
        sourceName: 'School Science Question Bank',
      },
    },
    {
      questionId: 'q_short_stomata_001',
      language: 'en',
      marks: 2,
      questionType: 'short_answer',
      rawText: 'State two functions of stomata.',
      content: {
        stem: [{ type: 'paragraph', text: 'State two functions of stomata.' }],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Life Processes'],
        topicNames: ['Stomata'],
        difficulty: 'easy',
        cbseRelevance: 'high',
      },
      source: {
        sourceType: 'previous_year_paper',
        sourceName: 'CBSE Science Sample Paper 2023',
        originalQuestionNumber: '6',
      },
    },
    {
      questionId: 'q_short_stomata_002',
      language: 'en',
      marks: 2,
      questionType: 'short_answer',
      rawText:
        'Why does transpiration help in upward movement of water in plants?',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'Why does transpiration help in upward movement of water in plants?',
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Life Processes'],
        topicNames: ['Transpiration'],
        difficulty: 'medium',
        cbseRelevance: 'medium',
      },
      source: {
        sourceType: 'question_bank',
        sourceName: 'School Science Question Bank',
      },
    },
    {
      questionId: 'q_short_electricity_001',
      language: 'en',
      marks: 2,
      questionType: 'short_answer',
      rawText: 'State Ohm law and write its mathematical form.',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'State Ohm law and write its mathematical form.',
          },
          { type: 'equation', latex: 'V = IR', text: 'V = IR' },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Physics',
        chapterNames: ['Electricity'],
        topicNames: ['Ohm Law'],
        difficulty: 'easy',
        cbseRelevance: 'high',
      },
      source: {
        sourceType: 'previous_year_paper',
        sourceName: 'CBSE Science 2022 Set 31/1/1',
      },
    },
    {
      questionId: 'q_short_electricity_002',
      language: 'en',
      marks: 2,
      questionType: 'short_answer',
      rawText:
        'A conductor has resistance 5 ohm. Find current when 10 V is applied.',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'A conductor has resistance 5 ohm. Find current when 10 V is applied.',
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Physics',
        chapterNames: ['Electricity'],
        topicNames: ['Ohm Law'],
        difficulty: 'medium',
        cbseRelevance: 'medium',
      },
      source: {
        sourceType: 'question_bank',
        sourceName: 'School Science Question Bank',
      },
    },
    {
      questionId: 'q_long_life_processes_001',
      language: 'en',
      marks: 5,
      questionType: 'long_answer',
      rawText:
        'Describe the pathway of blood through the human heart with labelled chambers.',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'Describe the pathway of blood through the human heart with labelled chambers.',
          },
        ],
        subparts: [
          {
            label: 'a',
            marks: 2,
            content: [
              {
                type: 'paragraph',
                text: 'Name the chambers receiving deoxygenated blood.',
              },
            ],
          },
          {
            label: 'b',
            marks: 2,
            content: [
              {
                type: 'paragraph',
                text: 'Trace the path of oxygenated blood.',
              },
            ],
          },
          {
            label: 'c',
            marks: 1,
            content: [
              { type: 'paragraph', text: 'Mention the role of valves.' },
            ],
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Life Processes'],
        topicNames: ['Human Heart'],
        difficulty: 'hard',
        cbseRelevance: 'high',
      },
      source: {
        sourceType: 'previous_year_paper',
        sourceName: 'CBSE Science 2024 Set 31/2/1',
      },
    },
    {
      questionId: 'q_long_life_processes_002',
      language: 'en',
      marks: 5,
      questionType: 'long_answer',
      rawText: 'Explain digestion in human beings with the role of enzymes.',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'Explain digestion in human beings with the role of enzymes.',
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Life Processes'],
        topicNames: ['Digestion'],
        difficulty: 'medium',
        cbseRelevance: 'medium',
      },
      source: {
        sourceType: 'question_bank',
        sourceName: 'School Science Question Bank',
      },
    },
    {
      questionId: 'q_long_internal_choice_001',
      language: 'en',
      marks: 5,
      questionType: 'long_answer',
      rawText: 'Attempt either option A or B from Life Processes.',
      content: {
        choices: [
          {
            displayStyle: 'or',
            chooseCount: 1,
            options: [
              {
                label: 'A',
                marks: 5,
                content: [
                  {
                    type: 'paragraph',
                    text: 'Explain the mechanism of breathing in human beings.',
                  },
                ],
              },
              {
                label: 'B',
                marks: 5,
                content: [
                  {
                    type: 'paragraph',
                    text: 'Explain the process of nutrition in amoeba.',
                  },
                ],
              },
            ],
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Life Processes'],
        topicNames: ['Respiration', 'Nutrition'],
        difficulty: 'hard',
        cbseRelevance: 'high',
      },
      source: {
        sourceType: 'previous_year_paper',
        sourceName: 'CBSE Science 2023 Set 31/3/2',
      },
    },
    {
      questionId: 'q_long_internal_choice_002',
      language: 'en',
      marks: 5,
      questionType: 'long_answer',
      rawText: 'Explain double circulation in human beings.',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'Explain double circulation in human beings.',
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Life Processes'],
        topicNames: ['Double Circulation'],
        difficulty: 'hard',
        cbseRelevance: 'medium',
      },
      source: {
        sourceType: 'question_bank',
        sourceName: 'School Science Question Bank',
      },
    },
    {
      questionId: 'q_case_brain_001',
      language: 'en',
      marks: 4,
      questionType: 'case_based',
      rawText:
        'Read the passage on human brain functions and answer the subparts.',
      content: {
        passage: [
          {
            type: 'paragraph',
            text: 'A student observes that some actions such as walking are voluntary while some actions such as breathing continue without conscious control.',
          },
        ],
        subparts: [
          {
            label: 'a',
            marks: 1,
            content: [{ type: 'paragraph', text: 'Define voluntary action.' }],
          },
          {
            label: 'b',
            marks: 1,
            content: [
              {
                type: 'paragraph',
                text: 'Name the part of brain controlling balance.',
              },
            ],
          },
          {
            label: 'c',
            marks: 2,
            content: [
              { type: 'paragraph', text: 'Explain the role of medulla.' },
            ],
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Control and Coordination'],
        topicNames: ['Human Brain'],
        difficulty: 'medium',
        cbseRelevance: 'high',
      },
      source: {
        sourceType: 'previous_year_paper',
        sourceName: 'CBSE Science 2024 Set 31/2/1',
      },
    },
    {
      questionId: 'q_case_brain_002',
      language: 'en',
      marks: 4,
      questionType: 'case_based',
      rawText: 'Read the passage on reflex actions and answer the subparts.',
      content: {
        passage: [
          {
            type: 'paragraph',
            text: 'A person immediately withdraws his hand after touching a hot object.',
          },
        ],
        subparts: [
          {
            label: 'a',
            marks: 1,
            content: [{ type: 'paragraph', text: 'Name this type of action.' }],
          },
          {
            label: 'b',
            marks: 1,
            content: [
              {
                type: 'paragraph',
                text: 'Which structure carries the impulse?',
              },
            ],
          },
          {
            label: 'c',
            marks: 2,
            content: [{ type: 'paragraph', text: 'Explain the reflex arc.' }],
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Biology',
        chapterNames: ['Control and Coordination'],
        topicNames: ['Reflex Action'],
        difficulty: 'medium',
        cbseRelevance: 'medium',
      },
      source: {
        sourceType: 'question_bank',
        sourceName: 'School Science Question Bank',
      },
    },
    {
      questionId: 'q_diagram_electricity_001',
      language: 'en',
      marks: 5,
      questionType: 'diagram_based',
      rawText: 'Observe the circuit diagram and answer the questions.',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'Observe the circuit diagram and answer the questions.',
          },
          {
            type: 'image_placeholder',
            text: 'Circuit diagram present in source PDF, extraction pending.',
          },
        ],
        subparts: [
          {
            label: 'a',
            marks: 2,
            content: [
              {
                type: 'paragraph',
                text: 'Identify the component connected in series.',
              },
            ],
          },
          {
            label: 'b',
            marks: 3,
            content: [
              { type: 'paragraph', text: 'Calculate equivalent resistance.' },
            ],
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Physics',
        chapterNames: ['Electricity'],
        topicNames: ['Series Circuit'],
        difficulty: 'hard',
        requiresDiagram: true,
        requiresCalculation: true,
        cbseRelevance: 'high',
      },
      source: {
        sourceType: 'previous_year_paper',
        sourceName: 'CBSE Science 2022 Set 31/1/1',
        pageNumber: 7,
      },
    },
    {
      questionId: 'q_diagram_electricity_002',
      language: 'en',
      marks: 5,
      questionType: 'diagram_based',
      rawText: 'Draw a labelled circuit diagram to verify Ohm law.',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'Draw a labelled circuit diagram to verify Ohm law.',
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Physics',
        chapterNames: ['Electricity'],
        topicNames: ['Ohm Law'],
        difficulty: 'medium',
        requiresDiagram: true,
        cbseRelevance: 'medium',
      },
      source: {
        sourceType: 'question_bank',
        sourceName: 'School Science Question Bank',
      },
    },
    {
      questionId: 'q_table_metals_001',
      language: 'en',
      marks: 5,
      questionType: 'table_based',
      rawText: 'Study the table of metals and answer the questions.',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'Study the table of metals and answer the questions.',
          },
          {
            type: 'table',
            rows: [
              ['Metal', 'Reaction with cold water'],
              ['Sodium', 'Vigorous'],
              ['Copper', 'No reaction'],
            ],
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Chemistry',
        chapterNames: ['Metals and Non-metals'],
        topicNames: ['Reactivity Series'],
        difficulty: 'medium',
        requiresTable: true,
        cbseRelevance: 'medium',
      },
      source: {
        sourceType: 'sample_paper',
        sourceName: 'CBSE Science Sample Paper 2024',
      },
    },
    {
      questionId: 'q_table_metals_002',
      language: 'en',
      marks: 5,
      questionType: 'table_based',
      rawText:
        'Compare the properties of metals and non-metals in tabular form.',
      content: {
        stem: [
          {
            type: 'paragraph',
            text: 'Compare the properties of metals and non-metals in tabular form.',
          },
        ],
      },
      metadata: {
        classLevel: '10',
        subject: 'Science',
        subjectArea: 'Chemistry',
        chapterNames: ['Metals and Non-metals'],
        topicNames: ['Physical Properties'],
        difficulty: 'easy',
        requiresTable: true,
        cbseRelevance: 'medium',
      },
      source: {
        sourceType: 'question_bank',
        sourceName: 'School Science Question Bank',
      },
    },
  ],
} satisfies PaperDocument;
