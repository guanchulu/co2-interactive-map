# Model Notes

This project uses reduced-order process simulation. Each pathway is evaluated
per tonne of captured CO2 entering the route.

## Carbon accounting

The LCA module distinguishes:

- captured CO2: CO2 entering the route
- utilized CO2: CO2 converted into product carbon or mineral carbon
- durably retained CO2: CO2 stored geologically or mineralized
- end-of-life CO2: product carbon released after use
- direct CO2 emissions: unconverted CO2 or side-product carbon emitted during processing

Net avoided emissions are calculated as:

```text
net_avoided = CO2_feed
              - (induced_process_emissions + end_of_life_release - displaced_product_credit)
```

This means short-lived fuels receive no permanent storage credit unless they
displace a fossil reference product and have low induced emissions.

## Economic accounting

Gross cost includes annualized CAPEX, electricity, hydrogen, heat, cooling,
transport, fixed OPEX, and variable OPEX. Net cost subtracts product revenue
and carbon credit:

```text
net_cost = gross_cost - product_revenue - carbon_credit
carbon_credit = max(0, net_avoided) * carbon_price
```

The default model credits avoided emissions, not only durable removals. For
policy analysis, this should be tested against a stricter durable-removal
crediting rule.

## Intended use

The model is appropriate for:

- pathway screening
- sensitivity analysis
- decision-map generation
- identifying research targets
- building tables for a TEA-LCA manuscript

It is not appropriate for final equipment design without calibration against
Aspen, pilot data, or detailed process design literature.

## Technology families

Thermochemical routes use heat and hydrogen to convert CO2 into methanol, CO,
or methane. Their main decision variables are hydrogen price, heat integration,
conversion/selectivity, recycle, and product purification.

Electrochemical routes are represented by stoichiometric reactors constrained
by Faradaic efficiency, cell voltage, single-pass conversion, and product
recovery. The model includes CO, formate, and ethylene representatives.

Photochemical and photoelectrochemical routes are represented by solar-to-
product efficiency, annual insolation, photoreactor area, reactor cost per
square meter, and downstream product recovery. These models are screening
representations because mature industrial design data are limited.
