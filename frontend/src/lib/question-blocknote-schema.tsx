/**
 * BlockNote schema for schema-aware Question editing.
 *
 * QPG blocks carry canonical region metadata in props while BlockNote owns
 * inline text editing, block movement, and deletion inside the focused overlay.
 *
 * @module questionBlockNoteSchema
 */
import { BlockNoteSchema, defaultBlockSpecs } from '@blocknote/core';
import { createReactBlockSpec } from '@blocknote/react';
import type { QuestionSemanticBlockType } from './question-editing';

const semanticProps = {
  regionKey: { default: '' },
  region: { default: '' },
  label: { default: '' },
  groupIndex: { default: -1 },
  marks: { default: -1 },
  itemJson: { default: '' },
} as const;

function inlineBlock(type: QuestionSemanticBlockType, label: string) {
  return createReactBlockSpec(
    {
      type,
      propSchema: semanticProps,
      content: 'inline',
    },
    {
      render: ({ block, contentRef }) => (
        <div
          className="qpg-semantic-block"
          data-region-key={block.props.regionKey}
        >
          <span className="qpg-semantic-block-label" contentEditable={false}>
            {block.props.label || label}
          </span>
          <span className="qpg-semantic-block-content" ref={contentRef} />
        </div>
      ),
    },
  )();
}

function atomicBlock(type: 'qpgImage' | 'qpgTable', label: string) {
  return createReactBlockSpec(
    {
      type,
      propSchema: semanticProps,
      content: 'none',
    },
    {
      render: ({ block }) => {
        const item = JSON.parse(block.props.itemJson || '{}') as {
          assetId?: string;
          caption?: string;
          rows?: string[][];
          text?: string;
        };
        if (type === 'qpgTable') {
          return (
            <div className="qpg-semantic-atomic">
              <span className="qpg-semantic-block-label">{label}</span>
              <table>
                <tbody>
                  {(item.rows ?? []).map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return (
          <figure className="qpg-semantic-atomic">
            <span className="qpg-semantic-block-label">{label}</span>
            <div>{item.caption ?? item.text ?? item.assetId ?? 'Diagram'}</div>
          </figure>
        );
      },
    },
  )();
}

export const questionBlockNoteSchema = BlockNoteSchema.create({
  blockSpecs: {
    ...defaultBlockSpecs,
    qpgStem: inlineBlock('qpgStem', 'Stem'),
    qpgPassage: inlineBlock('qpgPassage', 'Passage'),
    qpgAssertion: inlineBlock('qpgAssertion', 'Assertion'),
    qpgReason: inlineBlock('qpgReason', 'Reason'),
    qpgOption: inlineBlock('qpgOption', 'Option'),
    qpgSubpart: inlineBlock('qpgSubpart', 'Subpart'),
    qpgChoiceOption: inlineBlock('qpgChoiceOption', 'Choice'),
    qpgEquation: inlineBlock('qpgEquation', 'Equation'),
    qpgImage: atomicBlock('qpgImage', 'Image'),
    qpgTable: atomicBlock('qpgTable', 'Table'),
  },
});
