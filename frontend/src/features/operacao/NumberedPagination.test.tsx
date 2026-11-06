import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import NumberedPagination from "./NumberedPagination";

it("marca a página atual e navega por número e por seta", async () => {
  const user = userEvent.setup();
  const onPageChange = vi.fn();
  render(
    <NumberedPagination page={3} pageCount={7} onPageChange={onPageChange} />,
  );

  expect(screen.getByRole("button", { name: "Página 3" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(screen.getByRole("button", { name: "Página 2" })).not.toHaveAttribute(
    "aria-current",
  );

  await user.click(screen.getByRole("button", { name: "Página 7" }));
  expect(onPageChange).toHaveBeenLastCalledWith(7);
  await user.click(screen.getByRole("button", { name: "Próxima página" }));
  expect(onPageChange).toHaveBeenLastCalledWith(4);
  await user.click(screen.getByRole("button", { name: "Página anterior" }));
  expect(onPageChange).toHaveBeenLastCalledWith(2);
});

it("desabilita as setas nos extremos", () => {
  const { rerender } = render(
    <NumberedPagination page={1} pageCount={4} onPageChange={() => {}} />,
  );
  expect(
    screen.getByRole("button", { name: "Página anterior" }),
  ).toBeDisabled();
  expect(screen.getByRole("button", { name: "Próxima página" })).toBeEnabled();

  rerender(
    <NumberedPagination page={4} pageCount={4} onPageChange={() => {}} />,
  );
  expect(screen.getByRole("button", { name: "Próxima página" })).toBeDisabled();
});
