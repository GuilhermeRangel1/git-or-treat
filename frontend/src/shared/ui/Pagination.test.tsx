import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import Pagination from "./Pagination";

it("navega por números e permite alterar a quantidade por página", () => {
  const onPageChange = vi.fn();
  const onPageSizeChange = vi.fn();
  render(
    <Pagination
      page={5}
      totalPages={20}
      label="Paginação"
      pageSize={20}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
    />,
  );
  expect(screen.getByRole("button", { name: "Página 5" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    screen.queryByRole("button", { name: "Página 10" }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Página 6" }));
  fireEvent.change(screen.getByLabelText("Por página"), {
    target: { value: "50" },
  });
  expect(onPageChange).toHaveBeenCalledWith(6);
  expect(onPageSizeChange).toHaveBeenCalledWith(50);
});
