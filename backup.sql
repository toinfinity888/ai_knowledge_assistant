--
-- PostgreSQL database dump
--

-- Dumped from database version 17.2
-- Dumped by pg_dump version 17.5 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: evaluation_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.evaluation_logs (
    id integer NOT NULL,
    "timestamp" character varying,
    query character varying,
    context_recall character varying,
    faithfulness character varying,
    factual_correctness character varying
);


ALTER TABLE public.evaluation_logs OWNER TO postgres;

--
-- Name: evaluation_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.evaluation_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.evaluation_logs_id_seq OWNER TO postgres;

--
-- Name: evaluation_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.evaluation_logs_id_seq OWNED BY public.evaluation_logs.id;


--
-- Name: query_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.query_logs (
    id integer NOT NULL,
    query_text character varying,
    response_text character varying,
    has_response boolean NOT NULL,
    response_status character varying,
    response_time_ms integer,
    retriever_used character varying,
    llm_model_used character varying,
    retrieved_context json,
    user_id character varying,
    "timestamp" timestamp without time zone
);


ALTER TABLE public.query_logs OWNER TO postgres;

--
-- Name: query_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.query_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.query_logs_id_seq OWNER TO postgres;

--
-- Name: query_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.query_logs_id_seq OWNED BY public.query_logs.id;


--
-- Name: evaluation_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evaluation_logs ALTER COLUMN id SET DEFAULT nextval('public.evaluation_logs_id_seq'::regclass);


--
-- Name: query_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.query_logs ALTER COLUMN id SET DEFAULT nextval('public.query_logs_id_seq'::regclass);


--
-- Data for Name: evaluation_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.evaluation_logs (id, "timestamp", query, context_recall, faithfulness, factual_correctness) FROM stdin;
1	2025-05-14 08:49:31.541388	What is impact of covid	1.0	1.0	0.88
2	2025-05-14 10:35:16.858042	What is impact of covid	1.0	0.9411764706	0.85
\.


--
-- Data for Name: query_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.query_logs (id, query_text, response_text, has_response, response_status, response_time_ms, retriever_used, llm_model_used, retrieved_context, user_id, "timestamp") FROM stdin;
1	What is impact of covid	The COVID-19 pandemic may have a material adverse impact on the company's operational and financial performance. Factors such as the timing, extent, trajectory, and duration of the pandemic, the development and effectiveness of vaccines and treatments, the imposition of protective public safety measures, and the impact of the pandemic on the global economy and demand for their products are uncertain and beyond their control. The disruption in the global supply chain caused by the pandemic can also negatively affect their ability to proceed with clinical trials, preclinical development, and other activities, potentially delaying product approval and revenue generation. Furthermore, the continued spread of COVID-19 may lead to severe disruptions or volatility in the global capital markets, increasing the cost of capital and affecting their ability to access the capital markets. The ongoing COVID-19 pandemic can also negatively impact their business results and may heighten other risks and uncertainties mentioned in the risk factors section of their annual report.	t	OK	37931	SemanticSearch	mistral:instruct	["Table of Contents\\n- 73 -\\nImpact of COVID-19\\nTo date, the COVID-19 pandemic has not had a material adverse impact on our productivity or our business, and\\nas of December 31, 2022, we have not identified any significant disruption or impairment of our assets due to the\\npandemic. However, the extent to which the COVID-19 pandemic may impact our operational and financial performance\\nremains uncertain and will depend on many factors outside our control, including the timing, extent, trajectory and duration\\nof the pandemic, the emergence of new variants, the development, availability, distribution and effectiveness of vaccines\\nand treatments, the imposition of protective public safety measures, and the impact of the pandemic on the global economy\\nand demand for our products. To the extent the COVID-19 pandemic continues to disrupt economic activity globally, it\\ncould adversely affect our ability to access capital, which could in the future negatively affect our liquidity. As a result,\\nCOVID-", "Table of Contents\\nfor preclinical development and clinical trials, and the ability to raise capital when needed on acceptable terms, if at all. The COVID-19 pandemic\\ncontinues to impact the global supply chain, causing disruptions to service providers, logistics, and the flow and availability of supplies and products.\\nDisruptions in our operations or supply chain, whether as a result of government intervention, restricted travel, quarantine requirements, or otherwise, could\\nnegatively impact our ability to proceed with our clinical trials, preclinical development, and other activities and delay our ability to receive product\\napproval and generate revenue. In addition, the continued spread of COVID-19 may lead to severe disruption and volatility in the global capital markets,\\nwhich could increase our cost of capital and adversely affect our ability to access the capital markets. It is possible that the continued spread of COVID-19\\ncould cause an economic slowdown or recession or cause o", "bankruptcy. Any bankruptcy or insolvency, or the failure to make payments when due, of any counterparty of ours, or the loss of any significant \\nrelationships, could result in material losses to us and may material adverse impacts on our business.\\n \\nThe COVID-19 pandemic or future pandemics or public health crises could adversely impact our business, including our preclinical studies and \\nclinical trials.\\n\\u00a0\\n           Public health crises such as pandemics or similar outbreaks could adversely impact our business. The coronavirus, SARS-CoV-2, which causes \\nCOVID-19, and its variants have spread to every country in the world and throughout the United States and the United Kingdom. Many countries, as well \\nas most states of the United States, reacted by instituting quarantines, \\u201clockdowns\\u201d and other public health restrictions on leisure activities, work and travel. \\nAlthough pandemic-related restrictions have been eased or removed in most geographies, our business remains subject to pande", "COVID-19 and actions taken to reduce and manage its spread continue to evolve. The extent to which COVID-19 may impede the development of \\nour product candidates, reduce the productivity of our employees, disrupt our supply chains, delay our clinical trials, reduce our access to capital or limit \\nour business development activities, will depend on future developments and future mutations of COVID-19 or any other currently unknown infectious \\ndisease, which are highly uncertain and cannot be predicted with confidence. \\nIn addition, to the extent the ongoing COVID-19 pandemic adversely affects our business and results of operations, it may also have the effect of \\nheightening many of the other risks and uncertainties described in this Item 1A. \\u201cRisk Factors\\u201d section. \\nRisks related to the discovery and development of our product candidates \\nWe are early in our development efforts. Our business is heavily dependent on the successful development, regulatory approval and commercialization \\n", "Summary Risk Factors \\nYou should carefully read and consider the risk factors set forth under Item 1A, \\u201cRisk Factors,\\u201d as well as all other \\ninformation contained in this annual report on Form 10-K. Additional risks and uncertainties not presently known to us \\nor that we currently deem immaterial may also affect us. If any of these risks occur, our business, financial position, \\nresults of operations, cash flows or prospects could be materially, adversely affected. Our business is subject to the \\nfollowing principal risks and uncertainties: \\nRisks related to COVID-19 and other potential pandemics: \\n\\u2022  \\nCOVID-19 has affected, and may continue to affect, our operations. Further, COVID-19 could negatively \\nimpact our business, financial condition, and cash flows, particularly if it causes public health conditions \\nand/or economic conditions to deteriorate. \\n\\u2022  \\nWe are unable to predict the ultimate impact of the CARES Act (as defined below) and other stimulus and \\nrelief legislation or th"]	anonymous	2025-05-19 11:46:15.58746
\.


--
-- Name: evaluation_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.evaluation_logs_id_seq', 2, true);


--
-- Name: query_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.query_logs_id_seq', 1, true);


--
-- Name: evaluation_logs evaluation_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evaluation_logs
    ADD CONSTRAINT evaluation_logs_pkey PRIMARY KEY (id);


--
-- Name: query_logs query_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.query_logs
    ADD CONSTRAINT query_logs_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

