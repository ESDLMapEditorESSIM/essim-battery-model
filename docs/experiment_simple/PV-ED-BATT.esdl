<?xml version='1.0' encoding='UTF-8'?>
<esdl:EnergySystem xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:esdl="http://www.tno.nl/esdl" esdlVersion="v2102" description="" version="3" name="New Energy System" id="f89cd885-812c-44f9-80cc-5a7debd0cd66">
  <instance xsi:type="esdl:Instance" name="Untitled instance" id="23e5dacc-7a03-412d-b6ea-0abf7e4f8fdb">
    <area xsi:type="esdl:Area" name="Untitled area" id="e201d0c2-9292-4ef7-88a1-525fdf2c769c">
      <asset xsi:type="esdl:PVInstallation" id="208fdf01-0567-4880-900a-27a0cf423ce6" name="PVInstallation_208f">
        <geometry xsi:type="esdl:Point" lat="52.177477192076964" lon="5.267662703990937"/>
        <port xsi:type="esdl:OutPort" name="Out" id="5a84fa1e-3e97-4b5c-801a-0afbaa6e7671" connectedTo="ae3b3b9c-d946-4521-bd4d-ffedb26c1c26" carrier="7cb62d99-354a-4875-8a0f-284014270a42">
          <profile xsi:type="esdl:InfluxDBProfile" endDate="2020-01-01T00:00:00.000000+0100" multiplier="10.0" startDate="2019-01-01T00:00:00.000000+0100" filters="" id="e8015346-26b2-4344-9f03-5709caae2f0c" port="8086" measurement="standard_profiles" database="energy_profiles" host="http://influxdb" field="Zon_deBilt">
            <profileQuantityAndUnit xsi:type="esdl:QuantityAndUnitReference" reference="eb07bccb-203f-407e-af98-e687656a221d"/>
          </profile>
        </port>
      </asset>
      <asset xsi:type="esdl:ElectricityDemand" id="049578f4-8455-4e04-b099-808c013269cc" name="ElectricityDemand_0495">
        <geometry xsi:type="esdl:Point" CRS="WGS84" lat="52.17736044879581" lon="5.267423987388612"/>
        <port xsi:type="esdl:InPort" name="In" id="cf57d815-5134-4c8d-bc28-ae90291dd5bb" connectedTo="6b6a1568-4a27-42c7-be29-c54c382ae93a" carrier="7cb62d99-354a-4875-8a0f-284014270a42">
          <profile xsi:type="esdl:InfluxDBProfile" endDate="2020-01-01T00:00:00.000000+0100" multiplier="10.0" startDate="2019-01-01T00:00:00.000000+0100" filters="" id="5f6249cd-7184-4271-bdfe-eec6f5f77dcd" port="8086" measurement="standard_profiles" database="energy_profiles" host="http://influxdb" field="E1A">
            <profileQuantityAndUnit xsi:type="esdl:QuantityAndUnitReference" reference="eb07bccb-203f-407e-af98-e687656a221d"/>
          </profile>
        </port>
      </asset>
      <asset xsi:type="esdl:Battery" maxDischargeRate="2000.0" maxChargeRate="2000.0" capacity="21600000.0" id="BATT1" controlStrategy="cb3eb643-aec8-4351-b5bd-ac6e55b99a1f" name="Battery_6332">
        <geometry xsi:type="esdl:Point" CRS="WGS84" lat="52.17731934101993" lon="5.267835706472398"/>
        <port xsi:type="esdl:InPort" name="In" id="9194227f-28e1-493e-bb6f-b257852c6b45" connectedTo="6b6a1568-4a27-42c7-be29-c54c382ae93a" carrier="7cb62d99-354a-4875-8a0f-284014270a42"/>
      </asset>
      <asset xsi:type="esdl:Import" power="15000.0" id="9c087f17-cef8-4f84-9586-d1830597022b" name="Import_9c08">
        <costInformation xsi:type="esdl:CostInformation">
          <marginalCosts xsi:type="esdl:SingleValue" value="0.9" id="21d76101-4a9d-4932-bd04-c4523eaf2cb7" name="Import_9c08-MarginalCosts"/>
        </costInformation>
        <geometry xsi:type="esdl:Point" CRS="WGS84" lat="52.17696510979669" lon="5.268032848834992"/>
        <port xsi:type="esdl:OutPort" name="Out" id="1997b1bd-d617-45b5-b149-3872207d9aea" connectedTo="ae3b3b9c-d946-4521-bd4d-ffedb26c1c26" carrier="7cb62d99-354a-4875-8a0f-284014270a42"/>
      </asset>
      <asset xsi:type="esdl:ElectricityNetwork" id="e3a5d244-3cd7-45dd-b21d-98534e1b0ec3" name="ElectricityNetwork_e3a5">
        <geometry xsi:type="esdl:Point" CRS="WGS84" lat="52.17723469663029" lon="5.267719030380249"/>
        <port xsi:type="esdl:InPort" name="In" id="ae3b3b9c-d946-4521-bd4d-ffedb26c1c26" connectedTo="5a84fa1e-3e97-4b5c-801a-0afbaa6e7671 1997b1bd-d617-45b5-b149-3872207d9aea" carrier="7cb62d99-354a-4875-8a0f-284014270a42"/>
        <port xsi:type="esdl:OutPort" name="Out" id="6b6a1568-4a27-42c7-be29-c54c382ae93a" connectedTo="cf57d815-5134-4c8d-bc28-ae90291dd5bb 9194227f-28e1-493e-bb6f-b257852c6b45 7067144f-b820-4aac-a7aa-37285d7c2762" carrier="7cb62d99-354a-4875-8a0f-284014270a42"/>
      </asset>
      <asset xsi:type="esdl:Export" power="10000.0" id="ed410ace-e050-4ae2-a61e-4cad2e8c7bd3" name="Export_ed41">
        <costInformation xsi:type="esdl:CostInformation">
          <marginalCosts xsi:type="esdl:SingleValue" value="0.1" id="7417e9a2-e77c-41b4-a771-0195a068af94" name="Export_ed41-MarginalCosts"/>
        </costInformation>
        <geometry xsi:type="esdl:Point" CRS="WGS84" lat="52.17692557190003" lon="5.2678799629211435"/>
        <port xsi:type="esdl:InPort" name="In" id="7067144f-b820-4aac-a7aa-37285d7c2762" connectedTo="6b6a1568-4a27-42c7-be29-c54c382ae93a" carrier="7cb62d99-354a-4875-8a0f-284014270a42"/>
      </asset>
    </area>
  </instance>
  <services xsi:type="esdl:Services" id="94904bf1-ef47-44f6-862c-8bf9f30005b1">
    <service xsi:type="esdl:StorageStrategy" energyAsset="BATT1" id="cb3eb643-aec8-4351-b5bd-ac6e55b99a1f" name="StorageStrategy for Battery_6332">
      <marginalDischargeCosts xsi:type="esdl:SingleValue" value="0.8" id="64bfad37-8e14-415e-ba0d-acc25bb6e5bd" name="marginalChargeCosts for Battery_6332"/>
      <marginalChargeCosts xsi:type="esdl:SingleValue" value="0.2" id="8c8e505b-c3ea-4294-8e99-f4975b0edae8" name="marginalChargeCosts for Battery_6332"/>
    </service>
  </services>
  <energySystemInformation xsi:type="esdl:EnergySystemInformation" id="fdbcd299-5987-4473-9fd8-a4d94a27f247">
    <carriers xsi:type="esdl:Carriers" id="4c5bc116-29c8-49ff-9325-c2e3b4c6c332">
      <carrier xsi:type="esdl:ElectricityCommodity" name="Electricity" id="7cb62d99-354a-4875-8a0f-284014270a42"/>
    </carriers>
    <quantityAndUnits xsi:type="esdl:QuantityAndUnits" id="33403483-c00e-4c4a-ba87-8425870407e6">
      <quantityAndUnit xsi:type="esdl:QuantityAndUnitType" physicalQuantity="ENERGY" multiplier="GIGA" id="eb07bccb-203f-407e-af98-e687656a221d" description="Energy in GJ" unit="JOULE"/>
    </quantityAndUnits>
  </energySystemInformation>
</esdl:EnergySystem>
