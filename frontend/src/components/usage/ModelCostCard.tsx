type Props = {
  modelName: string;
  inputCost: number;
  outputCost: number;
  totalTokens: number;
  totalCost: number;
};

export function ModelCostCard({ modelName, inputCost, outputCost, totalTokens, totalCost }: Props) {
  return (
    <div className="model-cost-card">
      <h3>{modelName}</h3>
      <p>Input: ${inputCost}/1M tokens</p>
      <p>Output: ${outputCost}/1M tokens</p>
      <p>Total: {totalTokens.toLocaleString()} tokens (${totalCost.toFixed(4)})</p>
    </div>
  );
}
