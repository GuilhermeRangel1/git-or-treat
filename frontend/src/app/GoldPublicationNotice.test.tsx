import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import {
  markGoldPublicationStale,
  resetGoldPublication,
} from "@/shared/analytics/goldPublication";
import GoldPublicationNotice from "./GoldPublicationNotice";

beforeEach(resetGoldPublication);
it("refreshes analytic caches without erasing operational order history", async () => {
  const client = new QueryClient();
  client.setQueryData(["panorama", "old"], { revenue: 10 });
  client.setQueryData(["operations", "old"], { dec: 2 });
  client.setQueryData(["orders", "detail", 7], { version: 3 });
  markGoldPublicationStale();
  render(
    <QueryClientProvider client={client}>
      <GoldPublicationNotice />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Atualizar dados Gold" }));
  await waitFor(() =>
    expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
  );
  expect(client.getQueryData(["panorama", "old"])).toBeUndefined();
  expect(client.getQueryData(["operations", "old"])).toBeUndefined();
  expect(client.getQueryData(["orders", "detail", 7])).toEqual({ version: 3 });
});
