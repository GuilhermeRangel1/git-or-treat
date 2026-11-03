/**
 * Composição legal da Região Metropolitana do Recife conforme a relação do
 * IBGE publicada após a LC pernambucana nº 426/2020.
 *
 * `goldNames` registra somente nomes literais verificados no catálogo da
 * publicação Gold v2 aprovada para esta validação. Não há aproximação.
 */
export type TerritoryMunicipality = {
  code: string;
  name: string;
  goldNames: readonly string[];
};

export const municipalities: readonly TerritoryMunicipality[] = [
  { code: "2600054", name: "Abreu e Lima", goldNames: ["ABREU E LIMA"] },
  { code: "2601052", name: "Araçoiaba", goldNames: ["ARAÇOIABA"] },
  {
    code: "2602902",
    name: "Cabo de Santo Agostinho",
    goldNames: ["CABO DE SANTO AGOSTINHO"],
  },
  { code: "2603454", name: "Camaragibe", goldNames: ["CAMARAGIBE"] },
  { code: "2606804", name: "Igarassu", goldNames: ["IGARASSU"] },
  {
    code: "2607604",
    name: "Ilha de Itamaracá",
    goldNames: ["ILHA DE ITAMARACÁ"],
  },
  { code: "2607208", name: "Ipojuca", goldNames: ["IPOJUCA"] },
  { code: "2607752", name: "Itapissuma", goldNames: ["ITAPISSUMA"] },
  {
    code: "2607901",
    name: "Jaboatão dos Guararapes",
    goldNames: ["JABOATÃO DOS GUARARAPES"],
  },
  { code: "2609402", name: "Moreno", goldNames: ["MORENO"] },
  { code: "2609600", name: "Olinda", goldNames: ["OLINDA"] },
  { code: "2610707", name: "Paulista", goldNames: ["PAULISTA"] },
  { code: "2611606", name: "Recife", goldNames: ["RECIFE"] },
  {
    code: "2613701",
    name: "São Lourenço da Mata",
    goldNames: ["SÃO LOURENÇO DA MATA"],
  },
];

export function municipalityByCode(
  code: string,
): TerritoryMunicipality | undefined {
  return municipalities.find((municipality) => municipality.code === code);
}

export function municipalityByGoldName(
  name: string,
): TerritoryMunicipality | undefined {
  const matches = municipalities.filter(
    (municipality) =>
      municipality.name === name || municipality.goldNames.includes(name),
  );
  if (matches.length > 1)
    throw new Error(`Nome Gold ambíguo no registro: ${name}.`);
  return matches[0];
}

export function validateMunicipalityRegistry(
  entries: readonly TerritoryMunicipality[] = municipalities,
): void {
  const codes = new Set<string>();
  const names = new Set<string>();
  const mappedNames = new Map<string, string>();
  for (const entry of entries) {
    if (!/^\d{7}$/.test(entry.code))
      throw new Error(`Código IBGE inválido: ${entry.code}.`);
    if (codes.has(entry.code))
      throw new Error(`Código IBGE duplicado: ${entry.code}.`);
    if (!entry.name.trim())
      throw new Error(`Nome oficial ausente para ${entry.code}.`);
    if (names.has(entry.name))
      throw new Error(`Nome oficial duplicado: ${entry.name}.`);
    codes.add(entry.code);
    names.add(entry.name);
    for (const mappedName of [entry.name, ...entry.goldNames]) {
      if (!mappedName.trim())
        throw new Error(`Alias Gold vazio para ${entry.code}.`);
      const existingCode = mappedNames.get(mappedName);
      if (existingCode && existingCode !== entry.code)
        throw new Error(`Nome municipal ambíguo: ${mappedName}.`);
      mappedNames.set(mappedName, entry.code);
    }
  }
}

validateMunicipalityRegistry();
