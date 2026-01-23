const FORM_VERSION = "1.0.0";

const FORM_DEFINITION = {
  title: `Check-in formulier REM v${FORM_VERSION}`,
  sections: [
    {
      title: "Algemene informatie",
      description: "",
      fields: [
        {
          label: "Deelnemerscode",
          type: "text",
          required: true
        },
        {
          label: "Welke playlist luisterde je?",
          type: "multiple_choice",
          required: true,
          options: ["Calm", "Neutral", "Energy"]
        },
        {
          label: "Welke dag deed je een check-in?",
          type: "date",
          required: true
        },
        {
          label: "Starttijd?",
          type: "time",
          required: true
        },
        {
          label: "Eindtijd?",
          type: "time",
          required: true
        }
      ]
    },

    {
      title: "Gevoel bij start van Check-in",
      description: "",
      fields: [
        {
          label: "Welk gevoel had je?",
          type: "multiple_choice",
          required: true,
          options: [
            "Moe of ongemotiveerd",
            "Neutraal",
            "Gestresseerd of gespannen",
            "Anders"
          ]
        },
        {
          label: "Score van de intensiteit van je gevoel",
          type: "scale",
          required: true,
          scale_min: 1,
          scale_max: 10,
          scale_min_label: "Zwak",
          scale_max_label: "Sterk"
        }
      ]
    },

    {
      title: "Gevoel bij eind van Check-in",
      description: "",
      fields: [
        {
          label: "Welk gevoel had je?",
          type: "multiple_choice",
          required: true,
          options: [
            "Moe of ongemotiveerd",
            "Neutraal",
            "Gestresseerd of gespannen",
            "Anders"
          ]
        },
        {
          label: "Score van de intensiteit van je gevoel",
          type: "scale",
          required: true,
          scale_min: 1,
          scale_max: 10,
          scale_min_label: "Zwak",
          scale_max_label: "Sterk"
        }
      ]
    },

    {
      title: "Reflectie",
      description: "",
      fields: [
        {
          label: "Waren er specifieke nummers in de playlist die je gevoel beïnvloed hebben?",
          type: "long_text",
          required: false
        },
        {
          label: "Waren er specifieke momenten in de playlist die je opvielen?",
          type: "long_text",
          required: false
        }
      ]
    },

    {
      title: "Overige informatie",
      description: "",
      fields: [
        {
          label: "Waar heb je geluisterd?",
          type: "multiple_choice",
          required: true,
          options: ["Thuis", "Anders"]
        },
        {
          label: "Heb je de volledige playlist kunnen luisteren?",
          type: "multiple_choice",
          required: true,
          options: ["Ja", "Onderbroken", "Nee"]
        }
      ]
    },

    {
      title: "Toestemming",
      description:
        "Ik geef toestemming dat mijn data anoniem wordt verwerkt. De onderzoeksgegevens worden bewaard tot 15/06/2027. Uw contactgegevens worden gescheiden bewaard en vernietigd binnen 1 maand na afloop van het onderzoek. U kunt uw gegevens laten verwijderen tot 15/05/2026. Na deze datum zijn gegevens geanonimiseerd en niet meer traceerbaar.",
      fields: [
        {
          label:
            "Ik bevestig dat ik de informatie hierboven heb gelezen en ga akkoord.",
          type: "checkbox",
          required: true,
          options: [
            "Ik bevestig dat ik de informatie hierboven heb gelezen en ga akkoord."
          ]
        }
      ]
    }
  ]
};

function buildForm() {
  // 1. Maak een nieuw formulier
  const form = FormApp.create(FORM_DEFINITION.title);

  // 2. Loop over alle secties
  FORM_DEFINITION.sections.forEach(section => {
    const header = form.addSectionHeaderItem().setTitle(section.title);

    if (section.description) {
      header.setHelpText(section.description);
    }

    // 3. Loop over alle vragen in de sectie
    section.fields.forEach(field => {
      addFieldToForm(form, field);
    });
  });

  // 4. Toon de edit-URL in de logs
  Logger.log("Form created: " + form.getEditUrl());
}

function addFieldToForm(form, field) {
  switch (field.type) {
    case "text":
      form.addTextItem()
        .setTitle(field.label)
        .setRequired(field.required);
      break;

    case "long_text":
      form.addParagraphTextItem()
        .setTitle(field.label)
        .setRequired(field.required);
      break;

    case "multiple_choice":
      const mcItem = form.addMultipleChoiceItem()
        .setTitle(field.label)
        .setRequired(field.required);

      mcItem.setChoices(
        field.options.map(o => mcItem.createChoice(o))
      );
      break

    case "checkbox":
      const cbItem = form.addCheckboxItem()
        .setTitle(field.label)
        .setRequired(field.required);

      cbItem.setChoices(
        field.options.map(o => cbItem.createChoice(o))
      );
      break;


    case "date":
      form.addDateItem()
        .setTitle(field.label)
        .setRequired(field.required);
      break;

    case "time":
      form.addTimeItem()
        .setTitle(field.label)
        .setRequired(field.required);
      break;

    case "scale":
      form.addScaleItem()
        .setTitle(field.label)
        .setBounds(field.scale_min, field.scale_max)
        .setLabels(field.scale_min_label, field.scale_max_label)
        .setRequired(field.required);
      break;

    default:
      throw new Error("Onbekend veldtype: " + field.type);
  }
}
