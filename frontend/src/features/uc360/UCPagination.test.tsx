import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import UCPagination from "./UCPagination";

it("permite navegar por números e identifica a página atual em listas longas", () => {
  const onPageChange = vi.fn();
  render(
    <UCPagination
      page={5}
      totalPages={20}
      label="Paginação"
      onPageChange={onPageChange}
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
  expect(onPageChange).toHaveBeenCalledWith(6);
});
