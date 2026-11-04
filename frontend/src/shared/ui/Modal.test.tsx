import { createRef, useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Modal from "./Modal";

function Harness({
  header,
  description,
}: {
  header: "inline" | "sticky";
  description?: string;
}) {
  const triggerRef = createRef<HTMLButtonElement>();
  const [open, setOpen] = useState(true);
  return (
    <>
      <button ref={triggerRef} type="button">
        Abrir diálogo
      </button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title="Filtros"
        description={description}
        closeLabel="Fechar filtros"
        size="md"
        header={header}
      >
        <div>Conteúdo dos filtros</div>
      </Modal>
    </>
  );
}

describe("Modal", () => {
  it.each(["inline", "sticky"] as const)(
    "associa a descrição corretamente no cabeçalho %s",
    (header) => {
      render(<Harness header={header} description="Ajuste o recorte." />);
      const dialog = screen.getByRole("dialog", { name: "Filtros" });
      const description = screen.getByText("Ajuste o recorte.");
      expect(dialog).toHaveAttribute("aria-describedby", description.id);
      if (header === "sticky") {
        expect(description.tagName).toBe("P");
        expect(description.closest(".sticky")).not.toBeNull();
      }
    },
  );

  it.each(["inline", "sticky"] as const)(
    "não referencia descrição inexistente no cabeçalho %s",
    (header) => {
      render(<Harness header={header} />);
      expect(
        screen.getByRole("dialog", { name: "Filtros" }),
      ).not.toHaveAttribute("aria-describedby");
      expect(screen.getByText("Conteúdo dos filtros")).toBeVisible();
    },
  );

  it("fecha com Escape e devolve o foco ao controle que abriu", () => {
    render(<Harness header="sticky" description="Ajuste o recorte." />);
    const trigger = screen.getByRole("button", { name: "Abrir diálogo" });
    const dialog = screen.getByRole("dialog", { name: "Filtros" });

    fireEvent.keyDown(dialog, { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
