import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CollapseAll, CollapseButton, PhaseTotals } from "../components/PhaseCollapse";

const pc = { name: "Sviluppo", contingency_pct: "10.00", hours: "336.00", days: "42.00", days_with_contingency: "46.20", revenue: "30600.00", cost: "18360.00", contingency_revenue: "3060.00", revenue_with_contingency: "33660.00" };

describe("CollapseButton", () => {
  it("dice se la fase è aperta e cosa farà", async () => {
    const onClick = vi.fn();
    const { rerender } = render(<CollapseButton open onClick={onClick} name="la fase Sviluppo" />);
    const b = screen.getByRole("button", { name: "Comprimi la fase Sviluppo" });
    expect(b).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(b);
    expect(onClick).toHaveBeenCalledTimes(1);
    rerender(<CollapseButton open={false} onClick={onClick} name="la fase Sviluppo" />);
    expect(screen.getByRole("button", { name: "Espandi la fase Sviluppo" })).toHaveAttribute("aria-expanded", "false");
  });
});

describe("CollapseAll", () => {
  it("non compare con una sola fase", () => {
    render(<CollapseAll count={1} onCollapse={() => {}} onExpand={() => {}} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
  it("con più fasi chiude e riapre tutto", async () => {
    const [c, e] = [vi.fn(), vi.fn()];
    render(<CollapseAll count={3} onCollapse={c} onExpand={e} />);
    await userEvent.click(screen.getByRole("button", { name: "Comprimi tutte" }));
    await userEvent.click(screen.getByRole("button", { name: "Espandi tutte" }));
    expect([c.mock.calls.length, e.mock.calls.length]).toEqual([1, 1]);
  });
});

describe("PhaseTotals", () => {
  it("mostra ore, giorni, ricavo e costo, con giorni e ricavo comprensivi di contingency", () => {
    render(<PhaseTotals pc={pc} />);
    const t = within(screen.getByLabelText("Totali della fase"));
    expect(t.getByText("336,00")).toBeInTheDocument();
    expect(t.getByText("42,00")).toBeInTheDocument();
    expect(t.getByText("con cont. 46,20")).toBeInTheDocument();
    expect(t.getByText(/30\.600/)).toBeInTheDocument();
    expect(t.getByText(/con cont\..*33\.660/)).toBeInTheDocument();
    expect(t.getByText(/18\.360/)).toBeInTheDocument();
  });
  it("senza contingency non mostra le righe «con cont.»", () => {
    render(<PhaseTotals pc={{ ...pc, contingency_pct: "0.00" }} />);
    expect(screen.queryByText(/con cont\./)).not.toBeInTheDocument();
  });
  it("con il calcolo non aggiornato i totali sono attenuati", () => {
    render(<PhaseTotals pc={pc} stale />);
    expect(screen.getByLabelText("Totali della fase")).toHaveClass("opacity-50");
  });
});
